from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.response import SurveyResponse, Answer, AIAnalysisResult
from app.repositories.base import BaseRepository


class ResponseRepository(BaseRepository[SurveyResponse]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SurveyResponse, session)

    async def get_by_survey(self, survey_id: UUID) -> list[SurveyResponse]:
        result = await self.session.execute(
            select(SurveyResponse)
            .where(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.is_complete == True,  # noqa: E712
            )
            .options(selectinload(SurveyResponse.answers))
            .order_by(SurveyResponse.submitted_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_respondent_and_survey(
        self, respondent_id: UUID, survey_id: UUID
    ) -> SurveyResponse | None:
        result = await self.session.execute(
            select(SurveyResponse).where(
                SurveyResponse.respondent_id == respondent_id,
                SurveyResponse.survey_id == survey_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_text_answers_for_survey(self, survey_id: UUID) -> list[dict]:
        """Возвращает все текстовые ответы по опросу для AI-анализа."""
        from app.models.survey import Question, QuestionType
        result = await self.session.execute(
            select(Answer, Question.text.label("question_text"), SurveyResponse.respondent_id)
            .join(SurveyResponse, Answer.response_id == SurveyResponse.id)
            .join(Question, Answer.question_id == Question.id)
            .where(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.is_complete == True,  # noqa: E712
                Question.question_type == QuestionType.TEXT,
                Question.ai_analyze == True,  # noqa: E712
            )
        )
        rows = result.all()
        return [
            {
                "answer_id": str(row.Answer.id),
                "question_text": row.question_text,
                "text_value": row.Answer.text_value,
                "respondent_id": str(row.respondent_id) if row.respondent_id else None,
            }
            for row in rows
        ]


class AIAnalysisRepository(BaseRepository[AIAnalysisResult]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AIAnalysisResult, session)

    async def get_by_survey(self, survey_id: UUID) -> AIAnalysisResult | None:
        result = await self.session.execute(
            select(AIAnalysisResult).where(AIAnalysisResult.survey_id == survey_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, survey_id: UUID, result_data: dict) -> AIAnalysisResult:
        existing = await self.get_by_survey(survey_id)
        if existing:
            existing.result = result_data
            await self.session.flush()
            return existing
        new_result = AIAnalysisResult(survey_id=survey_id, result=result_data)
        return await self.create(new_result)
