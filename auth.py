from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os

logger = logging.getLogger("vyapar.auth")

# Cookie signing secret. Override in production via DASHBOARD_SECRET_KEY.
SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "dev-insecure-dashboard-secret").encode("utf-8")
SESSION_COOKIE = "vyapar_owner_session"

_PBKDF2_ROUNDS = 200_000


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds_s, salt_s, hash_s = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = _b64decode(salt_s)
        expected = _b64decode(hash_s)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def make_session_token(owner_id: int) -> str:
    msg = str(int(owner_id))
    sig = hmac.new(SECRET_KEY, msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"


def read_session_token(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    msg, _, sig = token.partition(".")
    expected = hmac.new(SECRET_KEY, msg.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return int(msg)
    except ValueError:
        return None
