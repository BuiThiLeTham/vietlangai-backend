from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_optional_user
from app.integrations.ml_client import MlClient, get_ml_client
from app.models import User
from app.schemas.translate import TranslateIn
from app.services import translate as translate_service

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post("")
async def translate_text(
    body: TranslateIn,
    db: AsyncSession = Depends(get_db),
    ml: MlClient = Depends(get_ml_client),
    user: User | None = Depends(get_optional_user),
) -> dict:
    return await translate_service.translate_text(db, ml, user, body)


@router.post("/image")
async def translate_image(
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    source_lang: str = Form("auto"),
    db: AsyncSession = Depends(get_db),
    ml: MlClient = Depends(get_ml_client),
    user: User | None = Depends(get_optional_user),
) -> dict:
    return await translate_service.translate_image(
        db,
        ml,
        user,
        file,
        source_lang=source_lang,
        target_lang=target_lang,
    )


@router.post("/speech")
async def translate_speech(
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    source_lang: str = Form("auto"),
    db: AsyncSession = Depends(get_db),
    ml: MlClient = Depends(get_ml_client),
    user: User | None = Depends(get_optional_user),
) -> dict:
    return await translate_service.translate_speech(
        db,
        ml,
        user,
        file,
        source_lang=source_lang,
        target_lang=target_lang,
    )


@router.get("/history")
async def translation_history(
    mode: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await translate_service.list_history(db, user, mode=mode, limit=limit, offset=offset)
