from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class AnswerCreate(BaseModel):
    question_id: UUID
    text_value: str | None = None
    selected_options: list[UUID] | None = None


class AnswerRead(BaseModel):
    id: UUID
    question_id: UUID
    text_value: str | None
    selected_options: list[str] | None

    model_config = {"from_attributes": True}


class SubmitSurveyRequest(BaseModel):
    answers: list[AnswerCreate]


class SurveyResponseRead(BaseModel):
    id: UUID
    survey_id: UUID
    respondent_id: UUID | None
    is_complete: bool
    started_at: datetime
    submitted_at: datetime | None
    answers: list[AnswerRead] = []

    model_config = {"from_attributes": True}
