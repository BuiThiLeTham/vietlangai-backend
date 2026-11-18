from pydantic import BaseModel


class AnswerIn(BaseModel):
    question_id: str
    choice_id: str


class QuizIn(BaseModel):
    answers: list[AnswerIn]
