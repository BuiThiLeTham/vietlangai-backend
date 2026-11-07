from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_optional_user
from app.integrations.ml_client import MlClient, MlError, get_ml_client
from app.models import Language, TranslationLog, User

router = APIRouter(prefix="/translate", tags=["translate"])
MAX_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 20 * 1024 * 1024


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source_lang: str = "auto"
    target_lang: str


def _ml_error(exc: MlError) -> HTTPException:
    status = 422 if exc.status == 422 else 400 if exc.status == 400 else 503
    return HTTPException(status_code=status, detail=exc.payload)


async def _known(db: AsyncSession, code: str) -> None:
    if code == "auto":
        return
    if await db.get(Language, code) is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "unknown_language", "message": f"Không có mã ngôn ngữ {code}."},
        )


async def _log(
    db: AsyncSession,
    user: User | None,
    mode: str,
    source_text: str,
    result: dict,
) -> None:
    db.add(
        TranslationLog(
            user_id=None if user is None else user.id,
            mode=mode,
            source_lang=result.get("source_lang", ""),
            target_lang=result.get("target_lang", ""),
            source_text=source_text[:4000],
            output_text=(result.get("text") or "")[:4000],
            route=result.get("route", ""),
            engine=result.get("engine", ""),
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()


def _recognized_only(recognized: dict, text: str, route: str, source_lang: str, target_lang: str, warnings: list[str]) -> dict:
    return {
        "text": "",
        "recognized_text": text,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "detected_lang": recognized.get("language"),
        "route": route,
        "engine": recognized.get("engine", "unloaded"),
        "warnings": warnings,
        "steps": [],
    }


async def _translate_recognized(
    db: AsyncSession,
    ml: MlClient,
    user: User | None,
    mode: str,
    route: str,
    recognized: dict,
    source_lang: str,
    target_lang: str,
) -> dict:
    """Translate text read by OCR or ASR. The recognized text is returned even
    when no translator exists yet for its language."""
    text = (recognized.get("text") or "").strip()
    warnings = list(recognized.get("warnings", []))
    if not text:
        return _recognized_only(recognized, "", route, source_lang, target_lang, warnings)
    text_lang = recognized.get("language")
    if text_lang:
        # A speech-translation checkpoint hears one language and writes another.
        spoken = recognized.get("spoken_language") or text_lang
        if source_lang not in ("auto", spoken):
            warnings.append(f"Mô hình giọng nói chỉ nghe được {spoken}, không phải {source_lang}.")
        source_lang = text_lang
    if source_lang == target_lang:
        result = _recognized_only(recognized, text, route, source_lang, target_lang, warnings)
        result["text"] = text
        await _log(db, user, mode, text, result)
        return result
    try:
        result = await ml.translate({"text": text, "source_lang": source_lang, "target_lang": target_lang})
    except MlError as exc:
        if exc.status != 422:
            raise _ml_error(exc) from exc
        message = exc.payload.get("message", "Chưa dịch được câu này.")
        return _recognized_only(recognized, text, route, source_lang, target_lang, [*warnings, message])
    result["recognized_text"] = text
    result["warnings"] = [*warnings, *result.get("warnings", [])]
    await _log(db, user, mode, text, result)
    return result


@router.post("")
async def translate_text(
    body: TranslateIn,
    db: AsyncSession = Depends(get_db),
    ml: MlClient = Depends(get_ml_client),
    user: User | None = Depends(get_optional_user),
) -> dict:
    await _known(db, body.source_lang)
    await _known(db, body.target_lang)
    try:
        result = await ml.translate(body.model_dump())
    except MlError as exc:
        raise _ml_error(exc) from exc
    await _log(db, user, "text", body.text, result)
    return result


@router.post("/image")
async def translate_image(
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    source_lang: str = Form("auto"),
    db: AsyncSession = Depends(get_db),
    ml: MlClient = Depends(get_ml_client),
    user: User | None = Depends(get_optional_user),
) -> dict:
    await _known(db, source_lang)
    await _known(db, target_lang)
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "Ảnh vượt 8 MB."})
    try:
        recognized = await ml.ocr(file.filename or "image", content, file.content_type or "")
    except MlError as exc:
        raise _ml_error(exc) from exc
    return await _translate_recognized(db, ml, user, "image", "ocr", recognized, source_lang, target_lang)


@router.post("/speech")
async def translate_speech(
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    source_lang: str = Form("auto"),
    db: AsyncSession = Depends(get_db),
    ml: MlClient = Depends(get_ml_client),
    user: User | None = Depends(get_optional_user),
) -> dict:
    await _known(db, source_lang)
    await _known(db, target_lang)
    content = await file.read(MAX_AUDIO_BYTES + 1)
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "Audio vượt 20 MB."})
    try:
        heard = await ml.asr(file.filename or "audio", content, file.content_type or "")
    except MlError as exc:
        raise _ml_error(exc) from exc
    return await _translate_recognized(db, ml, user, "speech", "asr", heard, source_lang, target_lang)
