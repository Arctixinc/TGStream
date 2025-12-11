# byte_streamer.py (patched)
import asyncio
from typing import Dict, Union
from pyrogram import Client, raw
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId
from TGLive.logger import LOGGER
from TGLive.helpers.exception import FIleNotFound
from TGLive.helpers.bot import work_loads, multi_clients
from TGLive.helpers.utils import get_file_ids  # use your robust helper


class ByteStreamer:
    def __init__(self, client: Client):
        self.client = client
        self.cache_ttl = 30 * 60
        self._cached_ids: Dict[int, FileId] = {}

        # start cache cleaner
        asyncio.create_task(self.clean_cache())

    async def get_file_properties(self, chat_id: int, msg_id: int) -> FileId:
        """Retrieve FileId (cached)."""
        if msg_id not in self._cached_ids:
            file_id = await get_file_ids(self.client, chat_id, msg_id)
            if not file_id:
                LOGGER.error(f"No file found for msg {msg_id}")
                raise FIleNotFound

            self._cached_ids[msg_id] = file_id

        return self._cached_ids[msg_id]

    async def yield_file(
        self,
        file_id: FileId,
        index: int,
        offset: int,
        chunk_size: int,
        part_count: int,
    ):
        """
        Yield raw file bytes fetched via upload.GetFile.
        Uses round-robin strategy across available clients for each chunk.
        """
        # protect against missing index in work_loads
        if index not in work_loads:
            work_loads[index] = 0

        work_loads[index] += 1

        try:
            client_ids = list(multi_clients.keys())
            if not client_ids:
                client_ids = [0]
                multi_clients[0] = self.client

            location = self.get_location(file_id)

            for part in range(part_count):
                # Round-robin selection of client
                current_client_id = client_ids[(index + part) % len(client_ids)]
                current_client = multi_clients.get(current_client_id, self.client)

                try:
                    media_session = await self.generate_media_session(current_client, file_id)
                    r = await media_session.send(
                        raw.functions.upload.GetFile(
                            location=location,
                            offset=offset,
                            limit=chunk_size
                        )
                    )
                except Exception as e:
                    LOGGER.error(f"Error calling GetFile with client {current_client_id}: {e}", exc_info=True)
                    break

                # `r` may be upload.File or other types
                if isinstance(r, raw.types.upload.File):
                    if not r.bytes:
                        break
                    yield r.bytes
                    offset += len(r.bytes)
                else:
                    break

        finally:
            # ensure we always decrement
            try:
                work_loads[index] -= 1
                if work_loads[index] < 0:
                    work_loads[index] = 0
            except Exception:
                work_loads[index] = 0

    async def generate_media_session(self, client: Client, file_id: FileId):
        media_session = client.media_sessions.get(file_id.dc_id)

        if media_session:
            return media_session

        from pyrogram.session import Session, Auth

        if file_id.dc_id != await client.storage.dc_id():
            media_session = Session(
                client,
                file_id.dc_id,
                await Auth(client, file_id.dc_id, await client.storage.test_mode()).create(),
                await client.storage.test_mode(),
                is_media=True
            )
            await media_session.start()

            for _ in range(6):
                exp = await client.invoke(raw.functions.auth.ExportAuthorization(dc_id=file_id.dc_id))
                try:
                    await media_session.send(
                        raw.functions.auth.ImportAuthorization(id=exp.id, bytes=exp.bytes)
                    )
                    break
                except AuthBytesInvalid:
                    continue
        else:
            media_session = Session(
                client,
                file_id.dc_id,
                await client.storage.auth_key(),
                await client.storage.test_mode(),
                is_media=True
            )
            await media_session.start()

        client.media_sessions[file_id.dc_id] = media_session
        return media_session

    def get_location(self, f: FileId):
        return raw.types.InputDocumentFileLocation(
            id=f.media_id,
            access_hash=f.access_hash,
            file_reference=f.file_reference,
            thumb_size=f.thumbnail_size
        )

    async def clean_cache(self):
        while True:
            await asyncio.sleep(self.cache_ttl)
            self._cached_ids.clear()
            LOGGER.debug("FileId cache cleared.")
