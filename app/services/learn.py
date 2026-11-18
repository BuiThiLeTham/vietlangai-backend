from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Lesson, QuizAttempt, QuizQuestion, User
from app.schemas.learn import QuizIn
from app.scoring import score_quiz
from app.serializers.learn import lesson_out


async def list_lessons(
    db: AsyncSession,
    *,
    language: str | None,
    level: str | None,
) -> list[dict]:
    query = select(Lesson).options(selectinload(Lesson.phrases)).order_by(Lesson.title_vi)
    if language:
        query = query.where(Lesson.language_code == language)
    if level:
        query = query.where(Lesson.level == level)
    rows = (await db.scalars(query)).all()
    return [lesson_out(row, with_questions=False) for row in rows]


async def my_progress(db: AsyncSession, user: User) -> dict:
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


async def get_lesson(db: AsyncSession, lesson_id: str) -> dict:
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
    return lesson_out(row, with_questions=True)


async def submit_quiz(
    db: AsyncSession,
    *,
    lesson_id: str,
    body: QuizIn,
    user: User | None,
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
