from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.survey import Survey, SurveyStatus
from app.repositories.base import BaseRepository


class SurveyRepository(BaseRepository[Survey]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Survey, session)

    async def get_by_id_with_questions(self, survey_id: UUID) -> Survey | None:
        result = await self.session.execute(
            select(Survey)
            .where(Survey.id == survey_id)
            .options(
                selectinload(Survey.questions)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_author(self, author_id: UUID) -> list[Survey]:
        result = await self.session.execute(
            select(Survey)
            .where(Survey.author_id == author_id)
            .order_by(Survey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_surveys(self) -> list[Survey]:
        result = await self.session.execute(
            select(Survey).where(Survey.status == SurveyStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def count_responses(self, survey_id: UUID) -> int:
        from app.models.response import SurveyResponse
        result = await self.session.execute(
            select(func.count(SurveyResponse.id)).where(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.is_complete == True,  # noqa: E712
            )
        )
        return result.scalar_one()

    async def get_all_with_stats(self) -> list[dict]:
        """Для панели администратора: все опросы со счётчиком ответов."""
        from app.models.response import SurveyResponse
        result = await self.session.execute(
            select(
                Survey,
                func.count(SurveyResponse.id).label("response_count"),
            )
            .outerjoin(
                SurveyResponse,
                (SurveyResponse.survey_id == Survey.id) & (SurveyResponse.is_complete == True),  # noqa: E712
            )
            .group_by(Survey.id)
            .order_by(Survey.created_at.desc())
        )
        rows = result.all()
        return [{"survey": row.Survey, "response_count": row.response_count} for row in rows]
