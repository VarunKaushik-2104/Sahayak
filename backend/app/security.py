"""Hashing and tokens. PINs and OTPs are never stored in the clear."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

import jwt

from . import clock
from .config import settings

ALGO = "HS256"


def _hash(secret: str, salt: bytes, rounds: int) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, rounds)
    return f"pbkdf2${rounds}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def hash_secret(secret: str) -> str:
    return _hash(secret, secrets.token_bytes(16), settings.pbkdf2_rounds)


def verify_secret(secret: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, rounds, salt, dk = stored.split("$")
        again = _hash(secret, base64.b64decode(salt), int(rounds))
    except Exception:
        return False
    return hmac.compare_digest(again, stored)


CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"      # no 0/O, 1/I/L: codes get read aloud and copied by hand


def make_code(n: int = 6) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(n))


def normalise_code(raw: str | None) -> str:
    return "".join(c for c in (raw or "").upper() if c.isalnum())


def normalise_email(raw: str) -> str:
    return raw.strip().lower()


def make_token(user_id: int, role: str) -> tuple[str, int]:
    life = timedelta(days=settings.token_days_student) if role == "student" else timedelta(hours=settings.token_hours_staff)
    exp = clock.now() + life
    tok = jwt.encode({"sub": str(user_id), "role": role, "exp": int(exp.timestamp()), "iat": int(clock.now().timestamp())},
                     settings.secret_key, algorithm=ALGO)
    return tok, int(life.total_seconds())


def read_token(token: str) -> dict:
    data = jwt.decode(token, settings.secret_key, algorithms=[ALGO], options={"verify_exp": False})
    if data["exp"] < int(clock.now().timestamp()):   # use our clock so tests can move time
        raise jwt.ExpiredSignatureError("token expired")
    return data