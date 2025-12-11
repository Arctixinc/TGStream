from os import environ
from typing import Optional, Tuple
from asyncio import gather, create_task, sleep

from TGLive.helpers.live_tg_client import LiveTgClient
from TGLive.helpers.bot import work_loads, multi_clients, LiveBot
from TGLive.logger import LOGGER
from TGLive.config import Telegram


from pyrogram import Client
from pyrogram.errors import AccessTokenExpired, FloodWait


class TokenParser:
    @staticmethod
    def parse_from_env():
        tokens = {
            c + 1: t
            for c, (_, t) in enumerate(
                filter(
                    lambda n: n[0].startswith("MULTI_TOKEN"),
                    sorted(environ.items())
                )
            )
        }
        return tokens

async def start_client(client_id: int, token: str) -> Optional[Tuple[int, Client]]:
    try:
        # LOGGER.info(f"[Client {client_id}] Starting initialization...")

        client = LiveTgClient(
            name=f"sessions/{client_id}",
            api_id=Telegram.API_ID,
            api_hash=Telegram.API_HASH,
            bot_token=token,
            sleep_threshold=120,
            no_updates=True,
            in_memory=False,
        )

        await client.start()

        work_loads[client_id] = 0

        # LOGGER.info(f"[Client {client_id}] Started successfully.")
        return client_id, client

    except AccessTokenExpired:
        LOGGER.warning(f"[Client {client_id}] Token expired — skipping.")
        return None

    except FloodWait as e:
        LOGGER.warning(f"[Client {client_id}] FloodWait {e.value}s — skipping this client.")
        await sleep(e.value)
        return None

    except Exception as e:
        LOGGER.error(f"[Client {client_id}] Failed to start — {e}", exc_info=True)
        return None



async def initialize_clients():
    multi_clients[0] = LiveBot
    work_loads[0] = 0

    all_tokens = TokenParser.parse_from_env()

    if not all_tokens:
        LOGGER.info("No MULTI_TOKEN found. Using only default bot client.")
        return

    LOGGER.info(f"Found {len(all_tokens)} additional clients. Starting...")

    tasks = [
        create_task(start_client(client_id, token))
        for client_id, token in all_tokens.items()
    ]

    results = await gather(*tasks, return_exceptions=True)

    started_clients = {}
    failed_clients = []

    for i, result in enumerate(results):
        client_id = list(all_tokens.keys())[i]

        if isinstance(result, Exception):
            LOGGER.error(f"[Client {client_id}] Crashed during startup: {result}")
            failed_clients.append(client_id)

        elif result is None:
            failed_clients.append(client_id)

        else:
            cid, client = result
            started_clients[cid] = client

    # Add successful clients
    multi_clients.update(started_clients)

    if started_clients:
        LOGGER.info(f"Successfully started: {list(started_clients.keys())}")

    if failed_clients:
        LOGGER.warning(f"Failed to start clients: {failed_clients}")

    if len(multi_clients) > 1:
        LOGGER.info(f"Multi-Client Mode ENABLED ({len(multi_clients)} active clients).")
    else:
        LOGGER.info("No additional clients started, using only default bot.")
