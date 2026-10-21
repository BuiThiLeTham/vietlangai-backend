import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models import Contribution, Language, User

router = APIRouter(tags=["community"])


class ContributionIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64)
    language_code: str
    source_lang: str
    target_lang: str
    source_text: str = Field(min_length=1, max_length=1000)
    target_text: str = Field(min_length=1, max_length=1000)
    note: str | None = Field(default=None, max_length=500)


class PushIn(BaseModel):
    contributions: list[ContributionIn] = Field(max_length=50)


class ReviewIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    review_note: str | None = Field(default=None, max_length=500)


def contribution_out(row: Contribution) -> dict:
    return {
        "id": row.id,
        "client_id": row.client_id,
        "language_code": row.language_code,
        "source_lang": row.source_lang,
        "target_lang": row.target_lang,
        "source_text": row.source_text,
        "target_text": row.target_text,
        "note": row.note,
        "status": row.status,
        "review_note": row.review_note,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


async def _require_languages(db: AsyncSession, *codes: str) -> None:
    for code in codes:
        if await db.get(Language, code) is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "unknown_language", "message": f"Không có mã ngôn ngữ {code}."},
            )


async def _save(db: AsyncSession, user: User, body: ContributionIn) -> Contribution:
    if body.source_lang == body.target_lang:
        raise HTTPException(
            status_code=400,
            detail={"code": "same_language", "message": "Câu nguồn và câu đích phải khác ngôn ngữ."},
        )
    await _require_languages(db, body.language_code, body.source_lang, body.target_lang)
    existing = await db.scalar(select(Contribution).where(Contribution.client_id == body.client_id))
    if existing is not None:
        if existing.user_id != user.id:
            raise HTTPException(
                status_code=409,
                detail={"code": "client_id_taken", "message": "Mã đóng góp đã thuộc người khác."},
            )
        return existing
    now = datetime.now(timezone.utc)
    row = Contribution(
        client_id=body.client_id,
        user_id=user.id,
        language_code=body.language_code,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        source_text=" ".join(body.source_text.split()),
        target_text=" ".join(body.target_text.split()),
        note=body.note,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


def _reviewer(user: User) -> User:
    if user.role != "reviewer":
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Chỉ người rà soát mới được duyệt câu."},
        )
    return user


@router.post("/contributions", status_code=201)
async def create_contribution(
    body: ContributionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await _save(db, user, body)
    await db.commit()
    await db.refresh(row)
    return contribution_out(row)


@router.get("/contributions/mine")
async def mine(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (
        await db.scalars(
            select(Contribution).where(Contribution.user_id == user.id).order_by(Contribution.created_at.desc())
        )
    ).all()
    return [contribution_out(row) for row in rows]


@router.get("/contributions")
async def queue(
    status: str = "pending",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    _reviewer(user)
    rows = (
        await db.scalars(select(Contribution).where(Contribution.status == status).order_by(Contribution.created_at))
    ).all()
    return [contribution_out(row) for row in rows]


@router.post("/contributions/{contribution_id}/review")
async def review(
    contribution_id: str,
    body: ReviewIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _reviewer(user)
    row = await db.get(Contribution, contribution_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy đóng góp."})
    row.status = body.status
    row.review_note = body.review_note
    row.reviewer_id = user.id
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return contribution_out(row)


@router.post("/sync/push")
async def push(
    body: PushIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    saved = []
    for item in body.contributions:
        saved.append(await _save(db, user, item))
    await db.commit()
    for row in saved:
        await db.refresh(row)
    return {"contributions": [contribution_out(row) for row in saved]}


@router.get("/sync/pull")
async def pull(db: AsyncSession = Depends(get_db)) -> dict:
    from sqlalchemy.orm import selectinload

    from app.models import EthnicGroup, Lesson, QuizQuestion
    from app.routers.catalog import heritage_out, language_out
    from app.routers.learn import _lesson

    languages = [language_out(row) for row in (await db.scalars(select(Language).order_by(Language.code))).all()]
    groups = (
        await db.scalars(select(EthnicGroup).options(selectinload(EthnicGroup.heritage)).order_by(EthnicGroup.slug))
    ).all()
    lessons = (
        await db.scalars(
            select(Lesson)
            .options(
                selectinload(Lesson.phrases),
                selectinload(Lesson.questions).selectinload(QuizQuestion.choices),
            )
            .order_by(Lesson.title_vi)
        )
    ).all()
    approved = (
        await db.scalars(select(Contribution).where(Contribution.status == "approved").order_by(Contribution.created_at))
    ).all()
    return {
        "languages": languages,
        "peoples": [
            {
                "slug": row.slug,
                "name_vi": row.name_vi,
                "name_en": row.name_en,
                "family": row.family,
                "region_vi": row.region_vi,
                "region_en": row.region_en,
                "origin_vi": row.origin_vi,
                "origin_en": row.origin_en,
                "language_code": row.language_code,
            }
            for row in groups
        ],
        "heritage": [
            {**heritage_out(item), "group_slug": row.slug} for row in groups for item in row.heritage
        ],
        "lessons": [_lesson(row, with_questions=True) for row in lessons],
        "approved_contributions": [contribution_out(row) for row in approved],
    }


@router.get("/training/pairs.csv", response_class=PlainTextResponse)
async def export_pairs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> str:
    _reviewer(user)
    rows = (
        await db.scalars(select(Contribution).where(Contribution.status == "approved").order_by(Contribution.created_at))
    ).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["source_lang", "target_lang", "source", "target", "verified"])
    for row in rows:
        writer.writerow([row.source_lang, row.target_lang, row.source_text, row.target_text, "true"])
    return buffer.getvalue()
