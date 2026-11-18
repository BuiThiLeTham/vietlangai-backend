import csv
import io
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.glossary_export import export_approved_glossary
from app.models import Contribution, EthnicGroup, Language, Lesson, Phrase, QuizQuestion, User
from app.schemas.community import ContributionIn, ReviewIn
from app.serializers.catalog import heritage_out, language_out, language_sort_key
from app.serializers.community import contribution_out
from app.serializers.learn import lesson_out
from app.services.languages import require_languages


async def require_ethnic_vi_pair(db: AsyncSession, body: ContributionIn) -> None:
    ethnic = await db.get(Language, body.language_code)
    if ethnic is None or ethnic.role != "ethnic":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ethnic_language_required",
                "message": "Đóng góp chỉ nhận cặp tiếng dân tộc ↔ tiếng Việt.",
            },
        )
    pair = {body.source_lang, body.target_lang}
    if pair != {body.language_code, "vi"}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ethnic_vi_only",
                "message": "Câu đóng góp phải là tiếng dân tộc ↔ tiếng Việt (không gửi cặp tiếng Anh).",
            },
        )


async def upsert_phrase_from_contribution(db: AsyncSession, row: Contribution) -> None:
    """Approved ethnic↔vi pairs become verified lesson phrases. Never invent text."""
    if row.status != "approved":
        return
    if {row.source_lang, row.target_lang} != {row.language_code, "vi"}:
        return
    if row.source_lang == row.language_code:
        native_text, vi_text = row.source_text, row.target_text
    else:
        native_text, vi_text = row.target_text, row.source_text
    lesson = await db.scalar(select(Lesson).where(Lesson.language_code == row.language_code).limit(1))
    if lesson is None:
        return
    existing = await db.scalar(
        select(Phrase).where(
            Phrase.lesson_id == lesson.id,
            Phrase.native_text == native_text,
            Phrase.vi_text == vi_text,
        )
    )
    if existing is not None:
        existing.verified = True
        existing.source = existing.source or f"contribution:{row.id}"
        return
    db.add(
        Phrase(
            lesson_id=lesson.id,
            native_text=native_text,
            vi_text=vi_text,
            en_text="",
            verified=True,
            source=f"contribution:{row.id}",
        )
    )


async def save_contribution(db: AsyncSession, user: User, body: ContributionIn) -> Contribution:
    if body.source_lang == body.target_lang:
        raise HTTPException(
            status_code=400,
            detail={"code": "same_language", "message": "Câu nguồn và câu đích phải khác ngôn ngữ."},
        )
    await require_languages(db, body.language_code, body.source_lang, body.target_lang)
    await require_ethnic_vi_pair(db, body)
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


async def list_mine(db: AsyncSession, user: User) -> list[dict]:
    rows = (
        await db.scalars(
            select(Contribution).where(Contribution.user_id == user.id).order_by(Contribution.created_at.desc())
        )
    ).all()
    return [contribution_out(row) for row in rows]


async def list_queue(
    db: AsyncSession,
    *,
    status: str,
    language_code: str | None,
) -> list[dict]:
    query = select(Contribution).where(Contribution.status == status)
    if language_code:
        query = query.where(Contribution.language_code == language_code)
    rows = (await db.scalars(query.order_by(Contribution.created_at))).all()
    return [contribution_out(row) for row in rows]


async def review_contribution(
    db: AsyncSession,
    *,
    contribution_id: str,
    body: ReviewIn,
    reviewer: User,
) -> dict:
    row = await db.get(Contribution, contribution_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy đóng góp."})
    if not get_settings().allow_self_review and reviewer.role != "admin" and row.user_id == reviewer.id:
        raise HTTPException(
            status_code=403,
            detail={"code": "self_review_forbidden", "message": "Không được tự duyệt câu đóng góp của chính mình."},
        )
    row.status = body.status
    row.review_note = body.review_note
    row.reviewer_id = reviewer.id
    row.updated_at = datetime.now(timezone.utc)
    if body.status == "approved":
        await upsert_phrase_from_contribution(db, row)
    await db.commit()
    if body.status == "approved":
        await export_approved_glossary(db)
    await db.refresh(row)
    return contribution_out(row)


async def push_contributions(db: AsyncSession, user: User, items: list[ContributionIn]) -> dict:
    saved = []
    for item in items:
        saved.append(await save_contribution(db, user, item))
    await db.commit()
    for row in saved:
        await db.refresh(row)
    return {"contributions": [contribution_out(row) for row in saved]}


async def pull_snapshot(db: AsyncSession, updated_after: datetime | None = None) -> dict:
    languages = [
        language_out(row) for row in (await db.scalars(select(Language).order_by(*language_sort_key()))).all()
    ]
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
    approved_query = select(Contribution).where(Contribution.status == "approved")
    if updated_after is not None:
        approved_query = approved_query.where(Contribution.updated_at >= updated_after)
    approved = (await db.scalars(approved_query.order_by(Contribution.created_at))).all()
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
        "lessons": [lesson_out(row, with_questions=True) for row in lessons],
        "approved_contributions": [contribution_out(row) for row in approved],
    }


async def export_training_pairs_csv(
    db: AsyncSession,
    *,
    language_code: str | None,
    source_lang: str | None,
    target_lang: str | None,
) -> str:
    query = select(Contribution).where(Contribution.status == "approved")
    if language_code:
        query = query.where(Contribution.language_code == language_code)
    if source_lang:
        query = query.where(Contribution.source_lang == source_lang)
    if target_lang:
        query = query.where(Contribution.target_lang == target_lang)
    rows = (await db.scalars(query.order_by(Contribution.created_at))).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["source_lang", "target_lang", "source", "target", "verified"])
    for row in rows:
        writer.writerow([row.source_lang, row.target_lang, row.source_text, row.target_text, "true"])
    return buffer.getvalue()
