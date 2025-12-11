from pyrogram import Client
from TGLive.config import Telegram
from TGLive.helpers.live_tg_client import LiveTgClient

LiveBot = Client(
    name='sessions/Livebot',
    api_id=Telegram.API_ID,
    api_hash=Telegram.API_HASH,
    bot_token=Telegram.BOT_TOKEN,
    plugins={"root": "TGLive/plugins"},
    sleep_threshold=20,
    workers=6,
    max_concurrent_transmissions=10
)


Helper = LiveTgClient(
    "sessions/helperbot",
    api_id=Telegram.API_ID,
    api_hash=Telegram.API_HASH,
    bot_token=Telegram.HELPER_BOT_TOKEN,
    sleep_threshold=20,
    workers=6,
    max_concurrent_transmissions=10
)


multi_clients = {}
work_loads = {}