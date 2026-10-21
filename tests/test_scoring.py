from types import SimpleNamespace

from app.scoring import score_quiz


def test_score_counts_only_matching_choice():
    questions = [
        SimpleNamespace(
            id="q1",
            explanation_vi="a",
            explanation_en="b",
            choices=[SimpleNamespace(id="ok", is_correct=True), SimpleNamespace(id="no", is_correct=False)],
        )
    ]
    assert score_quiz(questions, {"q1": "ok"})[0]["correct"] is True
    assert score_quiz(questions, {"q1": "no"})[0]["correct"] is False
    assert score_quiz(questions, {})[0]["correct"] is False
