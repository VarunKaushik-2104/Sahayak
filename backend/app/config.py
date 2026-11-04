"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


_SECRET_FILE_OK = [False]


def _load_secret() -> str:
    """SECRET_KEY if set. Otherwise a key kept in backend/.secret_key, so restarting the server does not sign everyone out."""
    env = os.getenv("SECRET_KEY")
    if env:
        return env
    f = BASE_DIR / ".secret_key"
    try:
        if f.exists() and len(f.read_text().strip()) >= 32:
            _SECRET_FILE_OK[0] = True
            return f.read_text().strip()
        key = secrets.token_urlsafe(48)
        f.write_text(key)
        try:
            f.chmod(0o600)
        except OSError:
            pass
        _SECRET_FILE_OK[0] = True
        return key
    except OSError:
        return secrets.token_urlsafe(48)


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'sahayak.db'}"))
    secret_key: str = field(default_factory=lambda: _load_secret())
    secret_is_ephemeral: bool = field(default_factory=lambda: not os.getenv("SECRET_KEY") and not _SECRET_FILE_OK[0])
    token_hours_staff: int = field(default_factory=lambda: int(os.getenv("TOKEN_HOURS_STAFF", "12")))
    token_days_student: int = field(default_factory=lambda: int(os.getenv("TOKEN_DAYS_STUDENT", "30")))
    # Demo data is for local development only. It is OFF unless SEED_DEMO=1, and sample rows are purged on start when it is off.
    seed_demo: bool = field(default_factory=lambda: _bool("SEED_DEMO", False))
    # Public address of the site (canonical links, sitemap, structured data). Falls back to the request's own host.
    site_url: str = field(default_factory=lambda: os.getenv("SITE_URL", "").rstrip("/"))
    contact_email: str = field(default_factory=lambda: os.getenv("CONTACT_EMAIL", ""))
    timezone: str = field(default_factory=lambda: os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
    cors_origins: list[str] = field(default_factory=lambda: [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o])
    curriculum_path: Path = field(default_factory=lambda: Path(os.getenv("CURRICULUM_PATH", BASE_DIR / "data" / "curriculum.json")))
    frontend_dir: Path = field(default_factory=lambda: Path(os.getenv("FRONTEND_DIR", REPO_DIR / "frontend")))
    pin_max_failures: int = 5
    pin_lock_minutes: float = field(default_factory=lambda: float(os.getenv("PIN_LOCK_MINUTES", "5")))
    staff_max_failures: int = 5
    feedback_per_hour: int = 5
    pbkdf2_rounds: int = field(default_factory=lambda: int(os.getenv("PBKDF2_ROUNDS", "200000")))


settings = Settings()
