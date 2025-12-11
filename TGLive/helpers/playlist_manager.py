# TGLive/helpers/playlist_manager.py  (replace generator)
from TGLive.logger import LOGGER
import asyncio

class PlaylistStreamGenerator:
    def __init__(self, playlist_manager, multi_streamer):
        self.pm = playlist_manager
        self.streamer = multi_streamer

    async def generator(self):
        current_id = None

        while True:
            # ask for next id first, then log it (clearer)
            next_id = await self.pm.next_video(current_id)
            LOGGER.info(f"Starting streaming for video: {next_id} (previous={current_id})")

            if next_id is None:
                await asyncio.sleep(1)
                continue

            current_id = next_id

            chunk_count = 0
            async for chunk in self.streamer.stream_video(self.pm.chat_id, current_id):
                chunk_count += 1
                # debug log every 10 chunks to avoid log spam, but show first chunk immediately
                if chunk_count == 1 or chunk_count % 10 == 0:
                    LOGGER.debug(f"Generator: video={current_id} chunk #{chunk_count} size={len(chunk) if chunk else 0} bytes")
                yield chunk

            LOGGER.info(f"Finished streaming video: {current_id} (chunks={chunk_count})")
