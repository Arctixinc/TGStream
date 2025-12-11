from TGLive.helpers.exception import FIleNotFound
from pyrogram.file_id import FileId
from TGLive.logger import LOGGER
from typing import Optional
from pyrogram import Client


# -------------------------
# MEDIA CHECKER
# -------------------------

def is_media(message):
    """Returns the media object if message contains any supported media."""
    media_attrs = [
        "document", "photo", "video", "audio",
        "voice", "video_note", "sticker", "animation"
    ]
    for attr in media_attrs:
        media = getattr(message, attr, None)
        if media:
            return media
    return None


# -------------------------
# FILE ID (FULL MEDIA DETAIL)
# -------------------------

async def get_file_ids(client: Client, chat_id: int, message_id: int) -> Optional[FileId]:
    """
    Returns a decoded FileId with additional attributes:
        - file_name
        - file_size
        - mime_type
        - unique_id
    Raises FIleNotFound when:
        - Message empty
        - No media in message
    """
    try:
        message = await client.get_messages(chat_id, message_id)

        if not message or message.empty:
            raise FIleNotFound("Message not found or empty")

        media = is_media(message)
        if not media:
            raise FIleNotFound("No supported media found in message")

        # Decode FileId
        file_id_obj = FileId.decode(media.file_id)

        # Add extra useful fields
        setattr(file_id_obj, "file_name", getattr(media, "file_name", None))
        setattr(file_id_obj, "file_size", getattr(media, "file_size", 0))
        setattr(file_id_obj, "mime_type", getattr(media, "mime_type", None))
        setattr(file_id_obj, "unique_id", media.file_unique_id)

        return file_id_obj

    except Exception as e:
        LOGGER.error(f"Error getting file IDs: {e}")
        raise


# -------------------------
# READABLE TIME FORMATTER
# -------------------------

def get_readable_time(seconds: int) -> str:
    """
    Converts seconds into a human-readable format:
    Example:
        65 -> "1m: 5s"
        3725 -> "1h: 2m: 5s"
        90000 -> "1 days, 1h: 0m"
    """

    count = 0
    readable_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", " days"]

    while count < 4:
        count += 1

        if count < 3:
            remainder, result = divmod(seconds, 60)  # seconds → minutes → hours
        else:
            remainder, result = divmod(seconds, 24)  # hours → days

        if seconds == 0 and remainder == 0:
            break

        time_list.append(int(result))
        seconds = int(remainder)

    # Attach suffix (s/m/h/days)
    for x in range(len(time_list)):
        time_list[x] = f"{time_list[x]}{time_suffix_list[x]}"

    # Days format: "X days,  HH:MM:SS"
    if len(time_list) == 4:
        readable_time += time_list.pop() + ", "

    time_list.reverse()
    readable_time += ": ".join(time_list)

    return readable_time
