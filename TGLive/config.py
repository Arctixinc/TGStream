from os import getenv, path
from dotenv import load_dotenv

load_dotenv(path.join(path.dirname(path.dirname(__file__)), "config.env"))

class Telegram:
    API_ID = int(getenv("API_ID", "11405252"))
    API_HASH = getenv("API_HASH", "b1a1fc3dc52ccc91781f33522255a880")
    BOT_TOKEN = getenv("BOT_TOKEN", "6326333011:AAHFsd404duVRtBJpFtKEGlWZkT14mUwQCM")
    
    HELPER_BOT_TOKEN = getenv("HELPER_BOT_TOKEN", "6441552101:AAELtzqFk9L-jFocRx1bRLqV3N0tgvwfb-U")

    BASE_URL = getenv("BASE_URL", "").rstrip('/')
    PORT = int(getenv("PORT", "8000"))
    DATABASE = [db.strip() for db in (getenv("DATABASE") or "").split(",") if db.strip()]


    UPSTREAM_REPO = getenv("UPSTREAM_REPO", "")
    UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "")

    OWNER_ID = int(getenv("OWNER_ID", "1881720028"))
    CHANNEL_ID = int(getenv("CHANNEL_ID", "-1001719899162"))

    MULTI_TOKEN1 = "8461823650:AAFGAtLCt-9Nn1sLZ73G0slCFm6wySrfZmM"
    MULTI_TOKEN2 = "8379790965:AAFVLnEcB2nTCpYoZ50jevejPIWXggrciQ0"
    MULTI_TOKEN3 = "8277438394:AAFWUh-2ykWZzK82YDlgYW9pM_4_uzajIRE"
    