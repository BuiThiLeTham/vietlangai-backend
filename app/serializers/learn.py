from app.models import Lesson, Phrase


def phrase_out(row: Phrase) -> dict:
    return {
        "id": row.id,
        "native_text": row.native_text,
        "vi_text": row.vi_text,
        "en_text": row.en_text,
        "source": row.source,
    }


def lesson_out(row: Lesson, *, with_questions: bool) -> dict:
    payload = {
        "id": row.id,
        "language_code": row.language_code,
        "title_vi": row.title_vi,
        "title_en": row.title_en,
        "summary_vi": row.summary_vi,
        "summary_en": row.summary_en,
        "level": row.level,
        "phrases": [phrase_out(item) for item in row.phrases if item.verified],
    }
    if with_questions:
        payload["questions"] = [
            {
                "id": question.id,
                "prompt_vi": question.prompt_vi,
                "prompt_en": question.prompt_en,
                "choices": [
                    {"id": choice.id, "text_vi": choice.text_vi, "text_en": choice.text_en}
                    for choice in question.choices
                ],
            }
            for question in row.questions
        ]
    return payload
