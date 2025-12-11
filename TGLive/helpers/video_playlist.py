import asyncio
from typing import List, Optional, Union
from pyrogram import types
from pyrogram.errors import FloodWait, AccessTokenExpired
from TGLive.logger import LOGGER


class VideoPlaylistManager:
    """
    Race-safe playlist manager with optional automatic update task.
    Maintains playlist newest → oldest.
    """

    def __init__(self, client, chat_id, auto_task: bool = True):
        self.client = client
        self.chat_id = chat_id

        self.playlist: List[int] = []
        self.latest_message_id: Optional[int] = None

        self._lock = asyncio.Lock()

        # NEW FLAG
        self.auto_task_flag: bool = auto_task
        self.auto_task: Optional[asyncio.Task] = None

    # ----------------------------------------------------------------------
    @staticmethod
    def is_video_message(msg: types.Message) -> bool:
        if not msg:
            return False
        if msg.video:
            return True
        if msg.document and msg.document.mime_type:
            return msg.document.mime_type.startswith("video/")
        return False

    # ======================================================================
    # PRIVATE HELPERS
    # ======================================================================
    async def _fetch_messages(self, limit: int):
        """Safe fetch: skips corrupted/unparseable messages."""
        try:
            messages = []
            async for msg in self.client.iter_messages(self.chat_id, limit=limit):
                try:
                    messages.append(msg)
                except Exception as e:
                    LOGGER.error(f"Skipping corrupt message: {e}")
                    continue

            return messages

        except FloodWait as e:
            LOGGER.warning(f"FloodWait {e.value}s during fetch.")
            await asyncio.sleep(e.value)
            return await self._fetch_messages(limit)

        except Exception as e:
            LOGGER.error(f"Unexpected message fetch error: {e}")
            return []

    # ------------------------------------------------------------------
    def _extract_video_ids(self, messages: List[types.Message]) -> List[int]:
        return [m.id for m in messages if self.is_video_message(m)]

    # ------------------------------------------------------------------
    async def _safe_update_playlist(self, new_list: List[int]):
        async with self._lock:
            self.playlist = new_list
            if new_list:
                self.latest_message_id = new_list[0]

    # ------------------------------------------------------------------
    async def _append_new_videos(self, new_ids: List[int]):
        async with self._lock:
            self.playlist = new_ids + self.playlist
            self.latest_message_id = max(new_ids)

    # ------------------------------------------------------------------
    def _find_index_safe(self, msg_id: int) -> Optional[int]:
        try:
            return self.playlist.index(msg_id)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    def _log_playlist_state(self):
        LOGGER.debug(f"Playlist size={len(self.playlist)} latest={self.latest_message_id}")
        
    # ------------------------------------------------------------------
    async def get_playlist(self) -> list:
        """Return a safe copy of the playlist."""
        async with self._lock:
            return list(self.playlist)  # return COPY, not reference


    # ======================================================================
    # PUBLIC METHODS
    # ======================================================================

    async def build_initial_playlist(self, limit: int = 2000):
        LOGGER.info("Building initial playlist...")

        messages = await self._fetch_messages(limit)
        messages.sort(key=lambda m: m.id, reverse=True)

        video_ids = self._extract_video_ids(messages)
        await self._safe_update_playlist(video_ids)

        LOGGER.info(f"Initial playlist built with {len(video_ids)} videos.")
        self._log_playlist_state()

        # AUTO START CHECKER IF FLAG ENABLED
        if self.auto_task_flag and not self.auto_task:
            self.auto_task = asyncio.create_task(self.start_auto_checker())

    # ----------------------------------------------------------------------
    async def check_for_new_videos(self, recent_limit: int = 500):
        if not self.latest_message_id:
            return await self.build_initial_playlist()

        messages = await self._fetch_messages(recent_limit)
        messages.sort(key=lambda m: m.id, reverse=True)

        new_ids = [
            msg.id for msg in messages
            if msg.id > self.latest_message_id and self.is_video_message(msg)
        ]

        if not new_ids:
            return

        new_ids.sort(reverse=True)
        await self._append_new_videos(new_ids)

        LOGGER.info(f"Added {len(new_ids)} new videos.")
        self._log_playlist_state()

    # ----------------------------------------------------------------------
    async def start_auto_checker(self):
        """Manually or auto-started periodic update task."""
        if self.auto_task is not None:
            return  # already running

        LOGGER.info("Auto-checker enabled (every 120s).")

        async def loop():
            while True:
                try:
                    await self.check_for_new_videos()
                except Exception as e:
                    LOGGER.error(f"Auto-checker error: {e}", exc_info=True)

                await asyncio.sleep(120)

        self.auto_task = asyncio.create_task(loop())

    # ----------------------------------------------------------------------
    async def manual_update(self):
        LOGGER.info("Manual playlist update requested.")
        await self.check_for_new_videos()

    # ----------------------------------------------------------------------
    async def next_video(self, current_id: Optional[int] = None) -> Optional[int]:
        async with self._lock:
            if not self.playlist:
                return None

            if current_id is None:
                return self.playlist[0]

            idx = self._find_index_safe(current_id)
            if idx is None:
                return self.playlist[0]

            next_index = (idx + 1) % len(self.playlist)
            return self.playlist[next_index]
