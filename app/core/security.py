import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _hasher.verify(password, hashed)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def create_access_token(user_id: str) -> tuple[str, int]:
    settings = get_settings()
    expires = settings.jwt_access_minutes * 60
    payload = {
        "sub": user_id,
        "typ": "access",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    settings = get_settings()
    jti = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_days)
    payload = {"sub": user_id, "typ": "refresh", "jti": jti, "exp": expires_at}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, hashlib.sha256(jti.encode()).hexdigest(), expires_at


def refresh_lookup(token: str) -> tuple[str, str]:
    payload = decode_token(token)
    if payload.get("typ") != "refresh" or "jti" not in payload:
        raise jwt.InvalidTokenError("refresh")
    digest = hashlib.sha256(payload["jti"].encode()).hexdigest()
    return payload["sub"], digest
