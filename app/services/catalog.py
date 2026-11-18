from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import EthnicGroup, HeritageItem, Language
from app.serializers.catalog import heritage_out, language_out, language_sort_key


async def list_languages(
    db: AsyncSession,
    *,
    role: str | None,
    q: str | None,
    limit: int | None,
    offset: int,
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


async def get_language(db: AsyncSession, code: str) -> dict:
    row = await db.get(Language, code)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy ngôn ngữ."})
    return language_out(row)


async def list_peoples(
    db: AsyncSession,
    *,
    language_code: str | None,
    family: str | None,
    q: str | None,
    limit: int | None,
    offset: int,
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


async def get_people(db: AsyncSession, slug: str) -> dict:
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


async def list_heritage(
    db: AsyncSession,
    *,
    group_slug: str | None,
    kind: str | None,
    q: str | None,
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
