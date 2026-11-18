from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_reviewer
from app.models import User
from app.schemas.community import ContributionIn, PushIn, ReviewIn
from app.serializers.community import contribution_out
from app.services import community as community_service

router = APIRouter(tags=["community"])


@router.post("/contributions", status_code=201)
async def create_contribution(
    body: ContributionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await community_service.save_contribution(db, user, body)
    await db.commit()
    await db.refresh(row)
    return contribution_out(row)


@router.get("/contributions/mine")
async def mine(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await community_service.list_mine(db, user)


@router.get("/contributions")
async def queue(
    status: str = "pending",
    language_code: str | None = None,
    user: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await community_service.list_queue(db, status=status, language_code=language_code)


@router.post("/contributions/{contribution_id}/review")
async def review(
    contribution_id: str,
    body: ReviewIn,
    user: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await community_service.review_contribution(
        db,
        contribution_id=contribution_id,
        body=body,
        reviewer=user,
    )


@router.post("/sync/push")
async def push(
    body: PushIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await community_service.push_contributions(db, user, body.contributions)


@router.get("/sync/pull")
async def pull(
    updated_after: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await community_service.pull_snapshot(db, updated_after)


@router.get("/training/pairs.csv", response_class=PlainTextResponse)
async def export_pairs(
    language_code: str | None = None,
    source_lang: str | None = None,
    target_lang: str | None = None,
    user: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> str:
    return await community_service.export_training_pairs_csv(
        db,
        language_code=language_code,
        source_lang=source_lang,
        target_lang=target_lang,
    )
