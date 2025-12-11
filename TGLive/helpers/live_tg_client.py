from typing import Dict, Tuple, Optional, AsyncGenerator, Union
from asyncio import gather, create_task
from pyrogram import Client, types
from pyrogram.errors import AccessTokenExpired, FloodWait


class LiveTgClient(Client):
    def __init__(
        self,
        name: str,
        api_id: int,
        api_hash: str,
        bot_token: str,
        sleep_threshold: int = 20,
        workers: int = 6,
        max_concurrent_transmissions: int = 10,
        **kwargs
    ):
        super().__init__(
            name=name,
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
            sleep_threshold=sleep_threshold,
            workers=workers,
            max_concurrent_transmissions=max_concurrent_transmissions,
            **kwargs
        )

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> AsyncGenerator["types.Message", None]:

        current = offset
        while current < limit:
            chunk = min(200, limit - current)
            msg_ids = list(range(current, current + chunk))

            messages = await self.get_messages(chat_id, msg_ids)

            for msg in messages:
                if msg is not None:
                    yield msg

            current += chunk

