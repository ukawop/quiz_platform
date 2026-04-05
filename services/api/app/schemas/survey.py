from uuid import UUID
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.survey import QuestionType, SurveyStatus


# ── Options ──────────────────────────────────────────────────────────────────

class QuestionOptionCreate(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=1024)]
    is_correct: bool = False


class QuestionOptionRead(BaseModel):
    id: UUID
    text: str
    order_index: int
    is_correct: bool

    model_config = {"from_attributes": True}


# ── Questions ─────────────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    text: Annotated[str, Field(min_length=1)]
    question_type: QuestionType
    ai_analyze: bool = False
    is_required: bool = True
    options: list[QuestionOptionCreate] = []


class QuestionRead(BaseModel):
    id: UUID
    text: str
    question_type: QuestionType
    order_index: int
    ai_analyze: bool
    is_required: bool
    options: list[QuestionOptionRead] = []

    model_config = {"from_attributes": True}


# ── Surveys ───────────────────────────────────────────────────────────────────

class SurveyCreate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=512)]
    description: str | None = None
    is_anonymous: bool = True
    ends_at: datetime | None = None
    questions: list[QuestionCreate] = []


class SurveyRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: SurveyStatus
    is_anonymous: bool
    ends_at: datetime | None
    created_at: datetime
    author_id: UUID
    questions: list[QuestionRead] = []

    model_config = {"from_attributes": True}


class SurveyShort(BaseModel):
    """Краткое представление опроса для списков."""
    id: UUID
    title: str
    status: SurveyStatus
    is_anonymous: bool
    created_at: datetime
    question_count: int = 0

    model_config = {"from_attributes": True}


class SurveyWithStats(BaseModel):
    survey: SurveyShort
    response_count: int
