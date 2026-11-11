"""Export approved community pairs into the ML glossary CSV path."""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Contribution


async def export_approved_glossary(session: AsyncSession) -> Path | None:
    settings = get_settings()
    raw = (settings.glossary_export_path or "").strip()
    if not raw:
        return None
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = (
        await session.scalars(
            select(Contribution).where(Contribution.status == "approved").order_by(Contribution.created_at)
        )
    ).all()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_lang", "target_lang", "source", "target", "verified"])
        for row in rows:
            writer.writerow(
                [row.source_lang, row.target_lang, row.source_text, row.target_text, "true"]
            )
    return path
