from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models import EthnicGroup, HeritageItem, Language

router = APIRouter(tags=["catalog"])


def language_sort_key():
    """Ethnic first (Latin before Cham script), then Vietnamese, then English."""
    return (
        case(
            (Language.role == "ethnic", 0),
            (Language.code == "vi", 1),
            else_=2,
        ),
        Language.evaluation_tier,
        case((Language.script == "Latn", 0), else_=1),
        Language.code,
    )


def language_out(row: Language) -> dict:
    return {
        "code": row.code,
        "iso639_3": row.iso639_3,
        "name_vi": row.name_vi,
        "name_en": row.name_en,
        "script": row.script,
        "family": row.family,
        "role": row.role,
        "evaluation_tier": row.evaluation_tier,
        "orthography": row.orthography,
    }


def heritage_out(row: HeritageItem) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "title_vi": row.title_vi,
        "title_en": row.title_en,
        "body_vi": row.body_vi,
        "body_en": row.body_en,
        "media_url": row.media_url,
    }


@router.get("/languages")
async def languages(
    role: str | None = None,
    q: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(Language).order_by(*language_sort_key())
    if role:
        query = query.where(Language.role == role)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Language.code.ilike(pattern),
                Language.name_vi.ilike(pattern),
                Language.name_en.ilike(pattern),
                Language.family.ilike(pattern),
            )
        )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    rows = (await db.scalars(query)).all()
    return [language_out(row) for row in rows]


@router.get("/languages/{code}")
async def language_detail(code: str, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(Language, code)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy ngôn ngữ."})
    return language_out(row)


@router.get("/peoples")
async def peoples(
    language_code: str | None = None,
    family: str | None = None,
    q: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(EthnicGroup).order_by(EthnicGroup.name_vi)
    if language_code:
        query = query.where(EthnicGroup.language_code == language_code)
    if family:
        query = query.where(EthnicGroup.family.ilike(f"%{family.strip()}%"))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                EthnicGroup.slug.ilike(pattern),
                EthnicGroup.name_vi.ilike(pattern),
                EthnicGroup.name_en.ilike(pattern),
                EthnicGroup.region_vi.ilike(pattern),
                EthnicGroup.region_en.ilike(pattern),
            )
        )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    rows = (await db.scalars(query)).all()
    return [
        {
            "slug": row.slug,
            "name_vi": row.name_vi,
            "name_en": row.name_en,
            "family": row.family,
            "region_vi": row.region_vi,
            "region_en": row.region_en,
            "language_code": row.language_code,
        }
        for row in rows
    ]


@router.get("/peoples/{slug}")
async def people_detail(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.scalar(
        select(EthnicGroup)
        .where(EthnicGroup.slug == slug)
        .options(selectinload(EthnicGroup.heritage))
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy dân tộc."})
    language = await db.get(Language, row.language_code)
    return {
        "slug": row.slug,
        "name_vi": row.name_vi,
        "name_en": row.name_en,
        "family": row.family,
        "region_vi": row.region_vi,
        "region_en": row.region_en,
        "origin_vi": row.origin_vi,
        "origin_en": row.origin_en,
        "language_code": row.language_code,
        "language": language_out(language) if language is not None else None,
        "heritage": [heritage_out(item) for item in row.heritage],
    }


@router.get("/heritage")
async def heritage_list(
    group_slug: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(HeritageItem, EthnicGroup.slug).join(EthnicGroup, HeritageItem.group_id == EthnicGroup.id)
    if group_slug:
        query = query.where(EthnicGroup.slug == group_slug)
    if kind:
        query = query.where(HeritageItem.kind == kind)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                HeritageItem.title_vi.ilike(pattern),
                HeritageItem.title_en.ilike(pattern),
                HeritageItem.body_vi.ilike(pattern),
                HeritageItem.body_en.ilike(pattern),
            )
        )
    query = query.order_by(EthnicGroup.slug, HeritageItem.title_vi)
    rows = (await db.execute(query)).all()
    return [{**heritage_out(item), "group_slug": slug} for item, slug in rows]
