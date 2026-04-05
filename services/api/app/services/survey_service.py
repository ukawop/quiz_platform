from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.survey import Survey, Question, QuestionOption, SurveyStatus, QuestionType
from app.models.user import User
from app.repositories.survey_repository import SurveyRepository
from app.schemas.survey import SurveyCreate, QuestionCreate


class SurveyService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = SurveyRepository(session)
        self._session = session

    async def create_survey(self, author: User, data: SurveyCreate) -> Survey:
        survey = Survey(
            title=data.title,
            description=data.description,
            is_anonymous=data.is_anonymous,
            ends_at=data.ends_at,
            author_id=author.id,
            status=SurveyStatus.DRAFT,
        )
        self._session.add(survey)
        await self._session.flush()

        for idx, q_data in enumerate(data.questions):
            await self._add_question(survey.id, q_data, idx)

        await self._session.flush()
        await self._session.refresh(survey)
        return survey

    async def _add_question(
        self, survey_id: UUID, q_data: QuestionCreate, order_index: int
    ) -> Question:
        question = Question(
            survey_id=survey_id,
            text=q_data.text,
            question_type=q_data.question_type,
            order_index=order_index,
            ai_analyze=q_data.ai_analyze,
            is_required=q_data.is_required,
        )
        self._session.add(question)
        await self._session.flush()

        if q_data.options:
            for opt_idx, opt in enumerate(q_data.options):
                option = QuestionOption(
                    question_id=question.id,
                    text=opt.text,
                    order_index=opt_idx,
                    is_correct=opt.is_correct,
                )
                self._session.add(option)

        return question

    async def get_survey(self, survey_id: UUID) -> Survey | None:
        return await self._repo.get_by_id_with_questions(survey_id)

    async def get_author_surveys(self, author_id: UUID) -> list[Survey]:
        return await self._repo.get_by_author(author_id)

    async def publish_survey(self, survey: Survey) -> Survey:
        survey.status = SurveyStatus.ACTIVE
        await self._session.flush()
        return survey

    async def close_survey(self, survey: Survey) -> Survey:
        survey.status = SurveyStatus.CLOSED
        await self._session.flush()
        return survey

    async def delete_survey(self, survey: Survey) -> None:
        """Удалить опрос и все связанные данные (каскадно через БД)."""
        await self._session.delete(survey)
        await self._session.flush()

    async def get_dashboard_stats(self) -> list[dict]:
        return await self._repo.get_all_with_stats()

    async def get_active_surveys(self) -> list[Survey]:
        surveys = await self._repo.get_active_surveys()
        now = datetime.now(timezone.utc)
        result = []
        for s in surveys:
            if s.ends_at and s.ends_at < now:
                s.status = SurveyStatus.CLOSED
            else:
                result.append(s)
        await self._session.flush()
        return result
