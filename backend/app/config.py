"""Central configuration. Values come from the project-root .env file (never committed)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
STORAGE_DIR = Path(os.environ.get("TAMHEED_STORAGE", DATA_DIR / "storage"))


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

# Branding — change here to rename the product everywhere (backend emails + video).
PRODUCT_NAME = os.environ.get("PRODUCT_NAME", "Tamheed")
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Rimal Engineering & Technology")

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR / 'tamheed.db'}")
# Invitation links: explicit setting > host's public URL (Render / Railway) > local development
APP_BASE_URL = (os.environ.get("APP_BASE_URL")
                or os.environ.get("RENDER_EXTERNAL_URL")
                or (f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}" if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else None)
                or "http://localhost:5710")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
# Safety net for the demo: invitations are only emailed to these addresses.
EMAIL_ALLOWLIST = {e.strip().lower() for e in os.environ.get("EMAIL_ALLOWLIST", "waadbader66@gmail.com").split(",") if e.strip()}

VIDEO_FPS = int(os.environ.get("VIDEO_FPS", "20"))
VIDEO_W = int(os.environ.get("VIDEO_W", "1280"))
VIDEO_H = int(os.environ.get("VIDEO_H", "720"))
GRADUATE_DAYS = int(os.environ.get("GRADUATE_DAYS", "21"))  # after completing onboarding, move to existing employees
COOKIE_SECURE = os.environ.get("COOKIE_SECURE") == "1"  # set to 1 when served over HTTPS
FRONTEND_DIST = ROOT / "frontend" / "dist"
DISABLE_WORKER = os.environ.get("DISABLE_WORKER") == "1"


def claude_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY))
