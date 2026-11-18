from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Language


async def require_known_language(
    db: AsyncSession,
    code: str,
    *,
    allow_auto: bool = False,
) -> None:
    if allow_auto and code == "auto":
        return
    if await db.get(Language, code) is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "unknown_language", "message": f"Không có mã ngôn ngữ {code}."},
        )


async def require_languages(db: AsyncSession, *codes: str) -> None:
    for code in codes:
        await require_known_language(db, code)
