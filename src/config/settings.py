"""Environment configuration and app-wide constants.

Everything here used to be read at the top of app.py. Keeping it in one module
leaves app.py as a thin entrypoint (Flask init + routes + run) and gives every
other package (media, content, analytics, notify, syndication, providers) a
single source for env-derived values.

`load_dotenv()` runs here, before any value is read, so ".env" (git-ignored) is
honoured no matter which module imports this one first - the old app.py loaded
it before reading these same values, so behaviour is unchanged.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Repo root: <root>/src/config/settings.py -> <root>/src/config -> <root>/src -> <root>
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Flask ---
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")

# --- Admin login ---
ADMIN_USERNAME = os.environ.get("BLOG_ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("BLOG_ADMIN_PASSWORD")

# --- Uploads ---
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "ogg", "mov", "avi", "mkv", "wmv", "mp3", "wav", "m4a", "aac", "flac", "oga", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"}

MEDIA_FOLDER = os.path.join(ROOT, "media")
os.makedirs(MEDIA_FOLDER, exist_ok=True)

UPLOAD_TOKEN = os.environ.get("UPLOAD_TOKEN", "").strip()

# --- Providers (pluggable storage + database backends) ---
# Each data kind is served by one backend: `local` (the filesystem media/ folder
# and a local mongod) or `cloud` (an HTTP upload endpoint and a
# MongoDB-compatible URL). Selection is config-only, so no code changes when a
# platform is swapped in - see src/providers/registry.py.
DEFAULT_BACKEND = os.environ.get("DEFAULT_BACKEND", "local").strip() or "local"
MEDIA_BACKEND = os.environ.get("MEDIA_BACKEND", "").strip()   # overrides DEFAULT_BACKEND for media
DB_BACKEND = os.environ.get("DB_BACKEND", "").strip()         # overrides DEFAULT_BACKEND for the database

# --- Cloud media upload (used when MEDIA_BACKEND=cloud) ---
# No cloud SDK: the `http` adapter PUTs/POSTs the bytes to this endpoint with an
# optional auth header. Set MEDIA_FORM_FIELD when the API wants multipart.
MEDIA_ADAPTER = os.environ.get("MEDIA_ADAPTER", "http").strip() or "http"
MEDIA_UPLOAD_URL = os.environ.get("MEDIA_UPLOAD_URL", "").strip()
MEDIA_UPLOAD_METHOD = os.environ.get("MEDIA_UPLOAD_METHOD", "PUT").strip().upper() or "PUT"
MEDIA_AUTH_HEADER = os.environ.get("MEDIA_AUTH_HEADER", "").strip()
MEDIA_TOKEN = os.environ.get("MEDIA_TOKEN", "").strip()
MEDIA_FORM_FIELD = os.environ.get("MEDIA_FORM_FIELD", "").strip()
# Public URL base for the links the cloud media backend builds (e.g. a CDN host).
MEDIA_PUBLIC_BASE = os.environ.get("MEDIA_PUBLIC_BASE", "").strip().rstrip("/")

# --- Cloud database (used when DB_BACKEND=cloud) ---
# Any MongoDB-compatible URL (Atlas / DocumentDB / Cosmos-Mongo). When empty, the
# local backend uses a local mongod at 127.0.0.1:27017/blog_db.
MONGO_URI = os.environ.get("MONGO_URI", "").strip()

# --- Syndication (POSSE) ---
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
# Alternative / next site URL — recorded for the planned move to a permanent
# domain. Canonical links and syndication keep using SITE_URL; this is noted
# only (no behaviour change).
SITE_URL_ALT = os.environ.get("SITE_URL_ALT", "").rstrip("/")

# --- Analytics — lightweight, first-party, no third party. ---
# Events land in data/analytics.jsonl (JSON Lines) by default, or in the Mongo
# `analytics` collection when ANALYTICS_STORE=mongo. Switch the env var when
# hosting - no code change needed. Only a salted sha-256 of the client IP is
# stored; set ANALYTICS_IP_SALT to isolate deployments.
ANALYTICS_STORE = os.environ.get("ANALYTICS_STORE", "file").strip().lower()
ANALYTICS_IP_SALT = os.environ.get("ANALYTICS_IP_SALT", "blog-analytics").strip()
ANALYTICS_LOG_FILE = os.path.join(ROOT, "data", "analytics.jsonl")
os.makedirs(os.path.dirname(ANALYTICS_LOG_FILE), exist_ok=True)
# Opt-in visitor geo (country/state). The raw IP is NEVER stored: geolocate_ip
# runs at beacon time (while the IP is in request scope) and only the resolved
# country/region/city plus the salted ip_hash are persisted. Free, no-key
# ip-api.com is used; look-ups are cached per IP for 24h.
ANALYTICS_GEO = os.environ.get("ANALYTICS_GEO", "1") == "1"

# --- Notifications (Telegram webhook alerts, optional) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

__all__ = [
    "ROOT",
    "SECRET_KEY",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "ALLOWED_EXTENSIONS",
    "MEDIA_FOLDER",
    "UPLOAD_TOKEN",
    "DEFAULT_BACKEND",
    "MEDIA_BACKEND",
    "DB_BACKEND",
    "MEDIA_ADAPTER",
    "MEDIA_UPLOAD_URL",
    "MEDIA_UPLOAD_METHOD",
    "MEDIA_AUTH_HEADER",
    "MEDIA_TOKEN",
    "MEDIA_FORM_FIELD",
    "MEDIA_PUBLIC_BASE",
    "MONGO_URI",
    "SITE_URL",
    "SITE_URL_ALT",
    "ANALYTICS_STORE",
    "ANALYTICS_IP_SALT",
    "ANALYTICS_LOG_FILE",
    "ANALYTICS_GEO",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]
