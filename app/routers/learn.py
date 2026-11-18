from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_optional_user
from app.models import User
from app.schemas.learn import QuizIn
from app.services import learn as learn_service

router = APIRouter(tags=["learn"])


@router.get("/lessons")
async def lessons(
    language: str | None = None,
    level: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await learn_service.list_lessons(db, language=language, level=level)


@router.get("/lessons/progress/me")
async def my_progress(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await learn_service.my_progress(db, user)


@router.get("/lessons/{lesson_id}")
async def lesson_detail(lesson_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    return await learn_service.get_lesson(db, lesson_id)


@router.post("/lessons/{lesson_id}/quiz")
async def quiz(
    lesson_id: str,
    body: QuizIn,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> dict:
    return await learn_service.submit_quiz(db, lesson_id=lesson_id, body=body, user=user)
