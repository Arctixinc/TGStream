import pytz
from logging import getLogger, FileHandler, StreamHandler, INFO, ERROR, Formatter, basicConfig
from datetime import datetime

IST = pytz.timezone("Asia/Kolkata")

class ISTFormatter(Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, IST)
        return dt.strftime(datefmt or "%d-%b-%y %I:%M:%S %p")

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s"

file_handler = FileHandler("log.txt", mode="w")
stream_handler = StreamHandler()

formatter = ISTFormatter(LOG_FORMAT, "%d-%b-%y %I:%M:%S %p")
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

basicConfig(
    handlers=[file_handler, stream_handler],
    level=INFO,
    format=LOG_FORMAT
)

getLogger("httpx").setLevel(ERROR)
getLogger("pyrogram").setLevel(ERROR)
getLogger("aiohttp.web").setLevel(ERROR)
getLogger("aiohttp.access").setLevel(ERROR)
getLogger("web_log").setLevel(ERROR)


LOGGER = getLogger(__name__)
LOGGER.setLevel(INFO)

LOGGER.info("Logger initialized with IST timezone.")
