from pyrogram import Client, filters
from pyrogram.types import Message
from TGLive import StartTime, __version__
from TGLive.logger import LOGGER
from TGLive.helpers.utils import get_readable_time
from TGLive.helpers.bot import work_loads, multi_clients
import time

def format_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    return f"{d}d {h}h {m}m {s}s"


@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client: Client, message: Message):

    # Uptime
    uptime = int(time.time() - StartTime)
    uptime_text = get_readable_time(uptime)


    # Reply message
    text = (
        f"**👋 Hello {message.from_user.mention}!**\n\n"
        f"🤖 **TgLive Bot is Running**\n"
        f"📦 **Version:** `{__version__}`\n"
        f"⏳ **Uptime:** `{uptime_text}`\n\n"
        f"Use this bot to manage streaming and helper features.\n"
        f"work_loads: {work_loads}\n"
        f"multi_clients: {len(multi_clients)}\n"
    )

    await message.reply_text(text, disable_web_page_preview=True)
