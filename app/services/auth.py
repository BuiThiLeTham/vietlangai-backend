import secrets
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    refresh_lookup,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas.auth import (
    ChangePasswordIn,
    GoogleIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserOut,
)


def bad_login() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "invalid_login", "message": "Email hoặc mật khẩu không đúng."},
    )


async def issue_tokens(session: AsyncSession, user: User) -> TokenOut:
    access, expires_in = create_access_token(user.id)
    refresh, digest, expires_at = create_refresh_token(user.id)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest,
            expires_at=expires_at,
        )
    )
    await session.commit()
    return TokenOut(access_token=access, refresh_token=refresh, expires_in=expires_in)


async def register(db: AsyncSession, body: RegisterIn) -> TokenOut:
    existing = await db.scalar(select(User).where(User.email == body.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "email_taken", "message": "Email đã được đăng ký."},
        )
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip(),
        role="member",
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return await issue_tokens(db, user)


async def login(db: AsyncSession, body: LoginIn) -> TokenOut:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise bad_login()
    return await issue_tokens(db, user)


async def google_login(db: AsyncSession, body: GoogleIn) -> TokenOut:
    settings = get_settings()
    allowed = {item.strip() for item in settings.google_client_ids.split(",") if item.strip()}
    if not allowed:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "google_not_configured",
                "message": "Đăng nhập Google chưa được cấu hình trên máy chủ.",
            },
        )
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": body.id_token},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "google_unreachable", "message": "Không xác minh được token Google."},
        ) from exc
    if response.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_google_token", "message": "Token Google không hợp lệ."},
        )
    payload = response.json()
    audience = str(payload.get("aud") or "")
    email = str(payload.get("email") or "").lower().strip()
    if audience not in allowed or not email or payload.get("email_verified") not in (True, "true"):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_google_token", "message": "Token Google không hợp lệ."},
        )
    display = str(payload.get("name") or email.split("@")[0]).strip()[:120] or "Thành viên"
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            display_name=display,
            role="member",
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
    return await issue_tokens(db, user)


async def refresh(db: AsyncSession, body: RefreshIn) -> TokenOut:
    try:
        user_id, digest = refresh_lookup(body.refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Phiên đăng nhập không hợp lệ."},
        ) from exc
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    now = datetime.now(timezone.utc)
    if stored is None or stored.revoked_at is not None or stored.user_id != user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Phiên đăng nhập không hợp lệ."},
        )
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Phiên đăng nhập không hợp lệ."},
        )
    stored.revoked_at = now
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Phiên đăng nhập không hợp lệ."},
        )
    return await issue_tokens(db, user)


async def logout(db: AsyncSession, body: RefreshIn) -> None:
    try:
        _user_id, digest = refresh_lookup(body.refresh_token)
    except Exception:
        return None
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        await db.commit()


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, display_name=user.display_name, role=user.role)


async def change_password(db: AsyncSession, user: User, body: ChangePasswordIn) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_password", "message": "Mật khẩu hiện tại không đúng."},
        )
    user.password_hash = hash_password(body.new_password)
    now = datetime.now(timezone.utc)
    active_tokens = (
        await db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    for tok in active_tokens:
        tok.revoked_at = now
    await db.commit()
