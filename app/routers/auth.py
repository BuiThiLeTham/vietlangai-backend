from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    refresh_lookup,
    verify_password,
)
from app.models import RefreshToken, User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str


def _bad_login() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "invalid_login", "message": "Email hoặc mật khẩu không đúng."},
    )


async def _issue(session: AsyncSession, user: User) -> TokenOut:
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


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
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
    return await _issue(db, user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise _bad_login()
    return await _issue(db, user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
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
    return await _issue(db, user)


@router.post("/logout", status_code=204)
async def logout(body: RefreshIn, db: AsyncSession = Depends(get_db)) -> None:
    try:
        _user_id, digest = refresh_lookup(body.refresh_token)
    except Exception:
        return None
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        await db.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, display_name=user.display_name, role=user.role)
