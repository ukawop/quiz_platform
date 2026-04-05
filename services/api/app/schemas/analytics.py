from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class AIAnalysisRead(BaseModel):
    id: UUID
    survey_id: UUID
    result: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class SurveyStatsRead(BaseModel):
    total_responses: int
    questions_stats: list[dict]


class DashboardItem(BaseModel):
    survey_id: UUID
    survey_title: str
    survey_status: str
    response_count: int
    created_at: datetime
