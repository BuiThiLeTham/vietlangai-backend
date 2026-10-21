import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class Language(Base):
    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    iso639_3: Mapped[str] = mapped_column(String(16))
    name_vi: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    script: Mapped[str] = mapped_column(String(32))
    family: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))
    evaluation_tier: Mapped[int]
    orthography: Mapped[str] = mapped_column(String(255))


class EthnicGroup(Base):
    __tablename__ = "ethnic_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    name_vi: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    family: Mapped[str] = mapped_column(String(120))
    region_vi: Mapped[str] = mapped_column(Text)
    region_en: Mapped[str] = mapped_column(Text)
    origin_vi: Mapped[str] = mapped_column(Text)
    origin_en: Mapped[str] = mapped_column(Text)
    language_code: Mapped[str] = mapped_column(ForeignKey("languages.code"))

    heritage: Mapped[list["HeritageItem"]] = relationship(back_populates="group")


class HeritageItem(Base):
    __tablename__ = "heritage_items"
    __table_args__ = (UniqueConstraint("group_id", "title_vi"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(ForeignKey("ethnic_groups.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    title_vi: Mapped[str] = mapped_column(String(200))
    title_en: Mapped[str] = mapped_column(String(200))
    body_vi: Mapped[str] = mapped_column(Text)
    body_en: Mapped[str] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    group: Mapped[EthnicGroup] = relationship(back_populates="heritage")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    language_code: Mapped[str] = mapped_column(ForeignKey("languages.code"))
    title_vi: Mapped[str] = mapped_column(String(200))
    title_en: Mapped[str] = mapped_column(String(200))
    summary_vi: Mapped[str] = mapped_column(Text)
    summary_en: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(16), default="basic")

    questions: Mapped[list["QuizQuestion"]] = relationship(back_populates="lesson")
    phrases: Mapped[list["Phrase"]] = relationship(back_populates="lesson")


class Phrase(Base):
    __tablename__ = "phrases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    native_text: Mapped[str] = mapped_column(Text)
    vi_text: Mapped[str] = mapped_column(Text)
    en_text: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lesson: Mapped[Lesson] = relationship(back_populates="phrases")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    prompt_vi: Mapped[str] = mapped_column(Text)
    prompt_en: Mapped[str] = mapped_column(Text)
    explanation_vi: Mapped[str] = mapped_column(Text)
    explanation_en: Mapped[str] = mapped_column(Text)

    lesson: Mapped[Lesson] = relationship(back_populates="questions")
    choices: Mapped[list["QuizChoice"]] = relationship(back_populates="question")


class QuizChoice(Base):
    __tablename__ = "quiz_choices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("quiz_questions.id", ondelete="CASCADE"))
    text_vi: Mapped[str] = mapped_column(String(255))
    text_en: Mapped[str] = mapped_column(String(255))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    question: Mapped[QuizQuestion] = relationship(back_populates="choices")


class TranslationLog(Base):
    __tablename__ = "translation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(16))
    source_lang: Mapped[str] = mapped_column(String(16))
    target_lang: Mapped[str] = mapped_column(String(16))
    source_text: Mapped[str] = mapped_column(Text)
    output_text: Mapped[str] = mapped_column(Text)
    route: Mapped[str] = mapped_column(String(32))
    engine: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Contribution(Base):
    __tablename__ = "contributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    language_code: Mapped[str] = mapped_column(ForeignKey("languages.code"))
    source_lang: Mapped[str] = mapped_column(String(16))
    target_lang: Mapped[str] = mapped_column(String(16))
    source_text: Mapped[str] = mapped_column(Text)
    target_text: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
