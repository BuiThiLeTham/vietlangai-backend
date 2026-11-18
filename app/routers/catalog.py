from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.services import catalog as catalog_service

router = APIRouter(tags=["catalog"])


@router.get("/languages")
async def languages(
    role: str | None = None,
    q: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await catalog_service.list_languages(db, role=role, q=q, limit=limit, offset=offset)


@router.get("/languages/{code}")
async def language_detail(code: str, db: AsyncSession = Depends(get_db)) -> dict:
    return await catalog_service.get_language(db, code)


@router.get("/peoples")
async def peoples(
    language_code: str | None = None,
    family: str | None = None,
    q: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await catalog_service.list_peoples(
        db,
        language_code=language_code,
        family=family,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/peoples/{slug}")
async def people_detail(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    return await catalog_service.get_people(db, slug)


@router.get("/heritage")
async def heritage_list(
    group_slug: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await catalog_service.list_heritage(db, group_slug=group_slug, kind=kind, q=q)
