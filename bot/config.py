import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set in environment variables.")

# Allowed Telegram user IDs for security
allowed_users_str = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = []
if allowed_users_str.strip():
    try:
        ALLOWED_USER_IDS = [int(uid.strip()) for uid in allowed_users_str.split(",") if uid.strip()]
    except ValueError:
        raise ValueError("ALLOWED_USER_IDS must be a comma-separated list of integers.")

# Transmission Config
TRANSMISSION_HOST = os.getenv("TRANSMISSION_HOST", "127.0.0.1")
try:
    TRANSMISSION_PORT = int(os.getenv("TRANSMISSION_PORT", "9091"))
except ValueError:
    TRANSMISSION_PORT = 9091

TRANSMISSION_USER = os.getenv("TRANSMISSION_USER", "") or None
TRANSMISSION_PASSWORD = os.getenv("TRANSMISSION_PASSWORD", "") or None
TRANSMISSION_PATH = os.getenv("TRANSMISSION_PATH", "/transmission/rpc")

DEFAULT_DOWNLOAD_DIR = os.getenv("DEFAULT_DOWNLOAD_DIR", "") or None
try:
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
except ValueError:
    POLL_INTERVAL = 10
