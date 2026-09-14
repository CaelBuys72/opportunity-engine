"""Lightweight two-operator auth + the single operator→credentials resolver.

Private internal app: exactly two operators (cael, sheylyn), verified server-side.
No signup / reset / OAuth. Passwords are PBKDF2-hashed in env vars; sessions are
opaque tokens stored in the storage backend (so they survive restarts / work across
instances). Local dev stays open (no login) until password hashes are configured,
so `python3 app/server.py` keeps working with zero setup.

SECRET RULE: provider API keys are read here, server-side only, and never returned
to callers, logged, or persisted. Frontend never sees them.
"""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import time

import storage

OPERATORS = ("cael", "sheylyn")
SESSION_TTL = 7 * 24 * 3600
COOKIE = "oe_session"


# ---------------------------------------------------------------- passwords
def hash_password(pw: str, iterations: int = 200_000) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${dk}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(iters)).hex()
        return hmac.compare_digest(calc, dk)
    except Exception:
        return False


def _password_hash(operator: str) -> str | None:
    return os.environ.get(f"{operator.upper()}_PASSWORD_HASH")


def auth_enabled() -> bool:
    """Auth is enforced once ANY operator password hash is configured (production)."""
    return any(_password_hash(op) for op in OPERATORS)


# ---------------------------------------------------------------- login / sessions
def login(operator: str, password: str) -> str | None:
    operator = (operator or "").strip().lower()
    if operator not in OPERATORS:
        return None
    h = _password_hash(operator)
    if not h or not verify_password(password, h):
        return None
    token = secrets.token_urlsafe(32)
    storage.get_backend().put_session(token, operator, time.time() + SESSION_TTL)
    return token


def resolve_session(token: str | None) -> str | None:
    """Return the authenticated operator for a session token, or None."""
    if not token:
        return None
    s = storage.get_backend().get_session(token)
    return s.get("operator") if s else None


def logout(token: str | None) -> None:
    if token:
        storage.get_backend().delete_session(token)


def current_operator(token: str | None) -> str | None:
    """Authoritative operator for a request. In open dev mode (no hashes configured)
    defaults to DEV_OPERATOR so local use needs no login."""
    if not auth_enabled():
        return os.environ.get("DEV_OPERATOR", "cael")
    return resolve_session(token)


# ---------------------------------------------------------------- credential resolver
class MissingCredential(Exception):
    pass


def resolve_operator_credentials(operator: str) -> dict:
    """The ONE place operator→keys happens. Never falls back to the other operator.
    Returns {'groq','gemini','cerebras','serper','together'} (str|None each). LLM work
    is routed per layer: product gen on Groq/Gemini, research on Cerebras. Server-side."""
    if operator not in OPERATORS:
        raise MissingCredential(f"unknown operator '{operator}'")
    up = operator.upper()
    groq = os.environ.get(f"{up}_GROQ_API_KEY")
    gem = os.environ.get(f"{up}_GEMINI_API_KEY")
    cer = os.environ.get(f"{up}_CEREBRAS_API_KEY")
    ser = os.environ.get(f"{up}_SERPER_API_KEY")
    tog = os.environ.get(f"{up}_TOGETHER_API_KEY")
    # local-dev convenience: fall back to the shared single-key names ONLY in open mode
    if not auth_enabled():
        groq = groq or os.environ.get("GROQ_API_KEY")
        gem = gem or os.environ.get("GEMINI_API_KEY")
        cer = cer or os.environ.get("CEREBRAS_API_KEY")
        ser = ser or os.environ.get("SERPER_API_KEY")
        tog = tog or os.environ.get("TOGETHER_API_KEY")
    return {"groq": groq, "gemini": gem, "cerebras": cer, "serper": ser,
            "together": tog, "operator": operator}
