from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ml_client import MlClient, MlError
from app.models import TranslationLog, User
from app.schemas.translate import TranslateIn
from app.services.languages import require_known_language

MAX_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 20 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "application/octet-stream",
}
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "video/mp4",
    "application/octet-stream",
}
ALLOWED_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".webm", ".flac"}


def validate_upload(
    content: bytes,
    filename: str | None,
    content_type: str | None,
    allowed_types: set[str],
    allowed_exts: set[str],
) -> None:
    if not content:
        raise HTTPException(
            status_code=400,
            detail={"code": "empty_file", "message": "Tệp tải lên đang rỗng."},
        )
    ctype = (content_type or "").split(";")[0].strip().lower()
    name = (filename or "").lower()
    ext_ok = any(name.endswith(ext) for ext in allowed_exts)
    type_ok = not ctype or ctype in allowed_types
    if not type_ok and not ext_ok:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_file_type", "message": "Định dạng tệp không được hỗ trợ."},
        )


def ml_error(exc: MlError) -> HTTPException:
    status = 422 if exc.status == 422 else 400 if exc.status == 400 else 503
    return HTTPException(status_code=status, detail=exc.payload)


async def log_translation(
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


def recognized_only(
    recognized: dict,
    text: str,
    route: str,
    source_lang: str,
    target_lang: str,
    warnings: list[str],
) -> dict:
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


async def translate_recognized(
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
        return recognized_only(recognized, "", route, source_lang, target_lang, warnings)
    text_lang = recognized.get("language")
    if text_lang:
        # A speech-translation checkpoint hears one language and writes another.
        spoken = recognized.get("spoken_language") or text_lang
        if source_lang not in ("auto", spoken):
            warnings.append(f"Mô hình giọng nói chỉ nghe được {spoken}, không phải {source_lang}.")
        source_lang = text_lang
    if source_lang == target_lang:
        result = recognized_only(recognized, text, route, source_lang, target_lang, warnings)
        result["text"] = text
        await log_translation(db, user, mode, text, result)
        return result
    try:
        result = await ml.translate({"text": text, "source_lang": source_lang, "target_lang": target_lang})
    except MlError as exc:
        if exc.status != 422:
            raise ml_error(exc) from exc
        message = exc.payload.get("message", "Chưa dịch được câu này.")
        return recognized_only(recognized, text, route, source_lang, target_lang, [*warnings, message])
    result["recognized_text"] = text
    result["warnings"] = [*warnings, *result.get("warnings", [])]
    await log_translation(db, user, mode, text, result)
    return result


async def translate_text(
    db: AsyncSession,
    ml: MlClient,
    user: User | None,
    body: TranslateIn,
) -> dict:
    await require_known_language(db, body.source_lang, allow_auto=True)
    await require_known_language(db, body.target_lang, allow_auto=True)
    try:
        result = await ml.translate(body.model_dump())
    except MlError as exc:
        raise ml_error(exc) from exc
    await log_translation(db, user, "text", body.text, result)
    return result


async def translate_image(
    db: AsyncSession,
    ml: MlClient,
    user: User | None,
    file: UploadFile,
    *,
    source_lang: str,
    target_lang: str,
) -> dict:
    await require_known_language(db, source_lang, allow_auto=True)
    await require_known_language(db, target_lang, allow_auto=True)
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "Ảnh vượt 8 MB."})
    validate_upload(content, file.filename, file.content_type, ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTS)
    try:
        recognized = await ml.ocr(file.filename or "image", content, file.content_type or "")
    except MlError as exc:
        raise ml_error(exc) from exc
    return await translate_recognized(db, ml, user, "image", "ocr", recognized, source_lang, target_lang)


async def translate_speech(
    db: AsyncSession,
    ml: MlClient,
    user: User | None,
    file: UploadFile,
    *,
    source_lang: str,
    target_lang: str,
) -> dict:
    await require_known_language(db, source_lang, allow_auto=True)
    await require_known_language(db, target_lang, allow_auto=True)
    content = await file.read(MAX_AUDIO_BYTES + 1)
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail={"code": "file_too_large", "message": "Audio vượt 20 MB."})
    validate_upload(content, file.filename, file.content_type, ALLOWED_AUDIO_TYPES, ALLOWED_AUDIO_EXTS)
    try:
        heard = await ml.asr(file.filename or "audio", content, file.content_type or "")
    except MlError as exc:
        raise ml_error(exc) from exc
    return await translate_recognized(db, ml, user, "speech", "asr", heard, source_lang, target_lang)


async def list_history(
    db: AsyncSession,
    user: User,
    *,
    mode: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    query = (
        select(TranslationLog)
        .where(TranslationLog.user_id == user.id)
        .order_by(TranslationLog.created_at.desc())
    )
    if mode:
        query = query.where(TranslationLog.mode == mode)
    query = query.offset(offset).limit(limit)
    rows = (await db.scalars(query)).all()
    return [
        {
            "id": row.id,
            "mode": row.mode,
            "source_lang": row.source_lang,
            "target_lang": row.target_lang,
            "source_text": row.source_text,
            "output_text": row.output_text,
            "route": row.route,
            "engine": row.engine,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
