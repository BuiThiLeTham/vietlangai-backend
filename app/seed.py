import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import (
    EthnicGroup,
    HeritageItem,
    Language,
    Lesson,
    QuizChoice,
    QuizQuestion,
    User,
)
from app.paths import load_catalog

NS = uuid.UUID("6f1d6b6a-1c1e-4a7a-9a1a-0c0a0a0a0a0a")
FAMILY_POOL = [
    "Tai-Kadai",
    "Austronesian, Chamic",
    "Hmong-Mien",
    "Austroasiatic, Vietic",
]
SCRIPT_LABELS = {
    "Latn": "Latin",
    "Cham": "Akhar Thrah (Cham)",
}
SCRIPT_POOL = ["Latin", "Akhar Thrah (Cham)", "Chữ Thái", "Chữ Nôm"]


def sid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


def _rotate(options: list[str], key: str) -> list[str]:
    shift = sum(ord(char) for char in key) % len(options)
    return options[shift:] + options[:shift]


async def seed(session: AsyncSession) -> None:
    catalog = load_catalog()
    languages = {row["code"]: row for row in catalog["languages"]}
    for row in catalog["languages"]:
        current = await session.get(Language, row["code"])
        values = dict(
            iso639_3=row["iso639_3"],
            name_vi=row["name_vi"],
            name_en=row["name_en"],
            script=row["script"],
            family=row["family"],
            role=row["role"],
            evaluation_tier=row["evaluation_tier"],
            orthography=row["orthography"],
        )
        if current is None:
            session.add(Language(code=row["code"], **values))
        else:
            for key, value in values.items():
                setattr(current, key, value)
    await session.flush()

    for row in catalog["peoples"]:
        language = languages[row["language_code"]]
        group = await session.scalar(select(EthnicGroup).where(EthnicGroup.slug == row["slug"]))
        if group is None:
            group = EthnicGroup(id=sid(f"people:{row['slug']}"), slug=row["slug"])
            session.add(group)
        group.name_vi = row["name_vi"]
        group.name_en = row["name_en"]
        group.family = language["family"]
        group.region_vi = row["region_vi"]
        group.region_en = row["region_en"]
        group.origin_vi = row["origin_vi"]
        group.origin_en = row["origin_en"]
        group.language_code = row["language_code"]
        await session.flush()
        await _ensure_heritage(session, group.id, row["slug"])
        await _ensure_lesson(session, group, language, catalog["peoples"])

    settings = get_settings()
    demo = await session.scalar(select(User).where(User.email == settings.demo_email))
    if demo is None:
        session.add(
            User(
                email=settings.demo_email,
                password_hash=hash_password(settings.demo_password),
                display_name=settings.demo_name,
                role="reviewer",
                created_at=datetime.now(timezone.utc),
            )
        )
    await session.commit()


async def _ensure_heritage(session: AsyncSession, group_id: str, slug: str) -> None:
    catalog = load_catalog()
    for item in catalog["heritage"]:
        if item["slug"] != slug:
            continue
        existing = await session.scalar(
            select(HeritageItem).where(
                HeritageItem.group_id == group_id,
                HeritageItem.title_vi == item["title_vi"],
            )
        )
        if existing is None:
            session.add(
                HeritageItem(
                    group_id=group_id,
                    kind=item["kind"],
                    title_vi=item["title_vi"],
                    title_en=item["title_en"],
                    body_vi=item["body_vi"],
                    body_en=item["body_en"],
                    media_url=None,
                )
            )


async def _ensure_lesson(session, group: EthnicGroup, language: dict, peoples: list[dict]) -> None:
    lesson_id = sid(f"lesson:{group.slug}")
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        lesson = Lesson(
            id=lesson_id,
            language_code=language["code"],
            title_vi=f"Làm quen với {language['name_vi']}",
            title_en=f"Getting started with {language['name_en']}",
            summary_vi=group.origin_vi,
            summary_en=group.origin_en,
            level="basic",
        )
        session.add(lesson)
        await session.flush()
        await _add_question(
            session,
            lesson_id,
            f"{group.slug}:family",
            f"{group.name_vi} nói ngôn ngữ thuộc họ nào?",
            f"Which family does the language of the {group.name_en} belong to?",
            language["family"],
            language["family"],
            [item for item in FAMILY_POOL if item != language["family"]],
            "Họ ngôn ngữ được ghi trong hồ sơ dân tộc.",
            "The family is stored on the people profile.",
        )
        script_label = SCRIPT_LABELS.get(language["script"], language["script"])
        await _add_question(
            session,
            lesson_id,
            f"{group.slug}:script",
            f"Chữ viết đang theo dõi cho {language['name_vi']} là gì?",
            f"Which writing system is tracked for {language['name_en']}?",
            script_label,
            script_label,
            [item for item in SCRIPT_POOL if item != script_label],
            language["orthography"],
            language["orthography"],
        )
        other_regions = [item["region_vi"] for item in peoples if item["slug"] != group.slug][:3]
        await _add_question(
            session,
            lesson_id,
            f"{group.slug}:region",
            f"{group.name_vi} sinh sống chủ yếu ở đâu?",
            f"Where do the {group.name_en} mainly live?",
            group.region_vi,
            group.region_en,
            other_regions,
            group.region_vi,
            group.region_en,
        )


async def _add_question(
    session,
    lesson_id: str,
    key: str,
    prompt_vi: str,
    prompt_en: str,
    correct_vi: str,
    correct_en: str,
    distractors: list[str],
    explanation_vi: str,
    explanation_en: str,
) -> None:
    question_id = sid(f"question:{key}")
    session.add(
        QuizQuestion(
            id=question_id,
            lesson_id=lesson_id,
            prompt_vi=prompt_vi,
            prompt_en=prompt_en,
            explanation_vi=explanation_vi,
            explanation_en=explanation_en,
        )
    )
    options = _rotate([correct_vi, *distractors[:3]], key)
    for label in options:
        session.add(
            QuizChoice(
                id=sid(f"choice:{key}:{label}"),
                question_id=question_id,
                text_vi=label,
                text_en=correct_en if label == correct_vi else label,
                is_correct=label == correct_vi,
            )
        )
