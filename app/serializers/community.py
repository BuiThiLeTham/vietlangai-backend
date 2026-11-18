from app.models import Contribution


def contribution_out(row: Contribution) -> dict:
    return {
        "id": row.id,
        "client_id": row.client_id,
        "language_code": row.language_code,
        "source_lang": row.source_lang,
        "target_lang": row.target_lang,
        "source_text": row.source_text,
        "target_text": row.target_text,
        "note": row.note,
        "status": row.status,
        "review_note": row.review_note,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
