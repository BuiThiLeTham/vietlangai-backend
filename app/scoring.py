def score_quiz(questions, answers: dict[str, str]) -> list[dict]:
    results = []
    for question in questions:
        correct = next((choice for choice in question.choices if choice.is_correct), None)
        chosen = answers.get(question.id)
        results.append(
            {
                "question_id": question.id,
                "correct": correct is not None and chosen == correct.id,
                "explanation_vi": question.explanation_vi,
                "explanation_en": question.explanation_en,
            }
        )
    return results
