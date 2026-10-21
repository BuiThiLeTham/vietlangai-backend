from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models import EthnicGroup, HeritageItem, Language

router = APIRouter(tags=["catalog"])


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
async def languages(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(Language).order_by(Language.evaluation_tier, Language.code))).all()
    return [language_out(row) for row in rows]


@router.get("/peoples")
async def peoples(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(EthnicGroup).order_by(EthnicGroup.name_vi))).all()
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
