from pydantic import BaseModel, Field


class ContributionIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64)
    language_code: str
    source_lang: str
    target_lang: str
    source_text: str = Field(min_length=1, max_length=1000)
    target_text: str = Field(min_length=1, max_length=1000)
    note: str | None = Field(default=None, max_length=500)


class PushIn(BaseModel):
    contributions: list[ContributionIn] = Field(max_length=50)


class ReviewIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    review_note: str | None = Field(default=None, max_length=500)
