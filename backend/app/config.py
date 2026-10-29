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


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'sahayak.db'}"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY") or secrets.token_urlsafe(48))
    secret_is_ephemeral: bool = field(default_factory=lambda: not os.getenv("SECRET_KEY"))
    token_hours_staff: int = field(default_factory=lambda: int(os.getenv("TOKEN_HOURS_STAFF", "12")))
    token_days_student: int = field(default_factory=lambda: int(os.getenv("TOKEN_DAYS_STUDENT", "30")))
    # SMS backend: "console" returns the OTP in the API response (demo only). A real provider plugs in via app.sms.
    sms_backend: str = field(default_factory=lambda: os.getenv("SMS_BACKEND", "console"))
    seed_demo: bool = field(default_factory=lambda: _bool("SEED_DEMO", True))
    timezone: str = field(default_factory=lambda: os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
    cors_origins: list[str] = field(default_factory=lambda: [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o])
    curriculum_path: Path = field(default_factory=lambda: Path(os.getenv("CURRICULUM_PATH", BASE_DIR / "data" / "curriculum.json")))
    frontend_dir: Path = field(default_factory=lambda: Path(os.getenv("FRONTEND_DIR", REPO_DIR / "frontend")))
    pin_max_failures: int = 5
    pin_lock_minutes: int = 5
    otp_minutes: int = 5
    otp_max_attempts: int = 5
    otp_requests_per_minute: int = 3
    pbkdf2_rounds: int = field(default_factory=lambda: int(os.getenv("PBKDF2_ROUNDS", "200000")))

    @property
    def demo_otp_visible(self) -> bool:
        return self.sms_backend == "console"


settings = Settings()
