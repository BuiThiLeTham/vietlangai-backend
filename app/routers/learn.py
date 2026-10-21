from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models import Lesson, Phrase, QuizQuestion
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
async def lessons(language: str | None = None, db: AsyncSession = Depends(get_db)) -> list[dict]:
    query = select(Lesson).options(selectinload(Lesson.phrases)).order_by(Lesson.title_vi)
    if language:
        query = query.where(Lesson.language_code == language)
    rows = (await db.scalars(query)).all()
    return [_lesson(row, with_questions=False) for row in rows]


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
async def quiz(lesson_id: str, body: QuizIn, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(selectinload(Lesson.questions).selectinload(QuizQuestion.choices))
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Không thấy bài học."})
    answers = {item.question_id: item.choice_id for item in body.answers}
    results = score_quiz(row.questions, answers)
    return {
        "score": sum(1 for item in results if item["correct"]),
        "total": len(results),
        "results": results,
    }
