from sqlalchemy import case

from app.models import HeritageItem, Language


def language_sort_key():
    """Ethnic first (Latin before Cham script), then Vietnamese, then English."""
    return (
        case(
            (Language.role == "ethnic", 0),
            (Language.code == "vi", 1),
            else_=2,
        ),
        Language.evaluation_tier,
        case((Language.script == "Latn", 0), else_=1),
        Language.code,
    )


def language_out(row: Language) -> dict:
    return {
        "code": row.code,
        "iso639_3": row.iso639_3,
        "name_vi": row.name_vi,
        "name_en": row.name_en,
        "script": row.script,
        "family": row.family,
        "role": row.role,
        "evaluation_tier": row.evaluation_tier,
        "orthography": row.orthography,
    }


def heritage_out(row: HeritageItem) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "title_vi": row.title_vi,
        "title_en": row.title_en,
        "body_vi": row.body_vi,
        "body_en": row.body_en,
        "media_url": row.media_url,
    }
