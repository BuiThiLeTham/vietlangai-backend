from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db, get_optional_user
from app.models import Lesson, Phrase, QuizAttempt, QuizQuestion, User
from app.scoring import score_quiz

router = APIRouter(tags=["learn"])


class AnswerIn(BaseModel):
    question_id: str
    choice_id: str


class QuizIn(BaseModel):
    answers: list[AnswerIn]


def _phrase(row: Phrase) -> dict:
    return {
        "id": row.id,
        "native_text": row.native_text,
        "vi_text": row.vi_text,
        "en_text": row.en_text,
        "source": row.source,
    }


def _lesson(row: Lesson, *, with_questions: bool) -> dict:
    payload = {
        "id": row.id,
        "language_code": row.language_code,
        "title_vi": row.title_vi,
        "title_en": row.title_en,
        "summary_vi": row.summary_vi,
        "summary_en": row.summary_en,
        "level": row.level,
        "phrases": [_phrase(item) for item in row.phrases if item.verified],
    }
    if with_questions:
        payload["questions"] = [
            {
                "id": question.id,
                "prompt_vi": question.prompt_vi,
                "prompt_en": question.prompt_en,
                "choices": [
                    {"id": choice.id, "text_vi": choice.text_vi, "text_en": choice.text_en}
                    for choice in question.choices
                ],
            }
            for question in row.questions
        ]
    return payload


@router.get("/lessons")
async def lessons(
    language: str | None = None,
    level: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(Lesson).options(selectinload(Lesson.phrases)).order_by(Lesson.title_vi)
    if language:
        query = query.where(Lesson.language_code == language)
    if level:
        query = query.where(Lesson.level == level)
    rows = (await db.scalars(query)).all()
    return [_lesson(row, with_questions=False) for row in rows]


@router.get("/lessons/progress/me")
async def my_progress(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    attempts = (
        await db.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user.id)
            .order_by(QuizAttempt.created_at.desc())
        )
    ).all()
    summary_by_lesson: dict[str, dict] = {}
    for item in attempts:
        entry = summary_by_lesson.get(item.lesson_id)
        if entry is None:
            summary_by_lesson[item.lesson_id] = {
                "lesson_id": item.lesson_id,
                "best_score": item.score,
                "total": item.total,
                "attempts_count": 1,
                "completed": item.total > 0 and item.score == item.total,
                "last_attempt_at": item.created_at.isoformat(),
            }
        else:
            entry["attempts_count"] += 1
            if item.score > entry["best_score"]:
                entry["best_score"] = item.score
                entry["completed"] = item.total > 0 and item.score == item.total
    return {
        "lessons_attempted": len(summary_by_lesson),
        "lessons_completed": sum(1 for item in summary_by_lesson.values() if item["completed"]),
        "progress": list(summary_by_lesson.values()),
        "history": [
            {
                "id": item.id,
                "lesson_id": item.lesson_id,
                "score": item.score,
                "total": item.total,
                "created_at": item.created_at.isoformat(),
            }
            for item in attempts
        ],
    }


@router.get("/lessons/{lesson_id}")
async def lesson_detail(lesson_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.phrases),
            selectinload(Lesson.questions).selectinload(QuizQuestion.choices),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy bài học."})
    return _lesson(row, with_questions=True)


@router.post("/lessons/{lesson_id}/quiz")
async def quiz(
    lesson_id: str,
    body: QuizIn,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    row = await db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(selectinload(Lesson.questions).selectinload(QuizQuestion.choices))
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy bài học."})
    answers = {item.question_id: item.choice_id for item in body.answers}
    results = score_quiz(row.questions, answers)
    score_val = sum(1 for item in results if item["correct"])
    total_val = len(results)
    if user is not None:
        db.add(
            QuizAttempt(
                user_id=user.id,
                lesson_id=lesson_id,
                score=score_val,
                total=total_val,
                created_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
    return {
        "score": score_val,
        "total": total_val,
        "results": results,
    }
