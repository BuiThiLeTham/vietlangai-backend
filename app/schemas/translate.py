from pydantic import BaseModel, Field


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source_lang: str = "auto"
    target_lang: str
