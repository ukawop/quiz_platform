from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.response import SurveyResponse, Answer
from app.models.survey import Survey, SurveyStatus
from app.repositories.response_repository import ResponseRepository
from app.schemas.response import SubmitSurveyRequest


class ResponseService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ResponseRepository(session)
        self._session = session

    async def start_response(
        self, survey: Survey, respondent_id: UUID | None
    ) -> SurveyResponse:
        """Создаёт незавершённое прохождение опроса."""
        if survey.status != SurveyStatus.ACTIVE:
            raise ValueError("Опрос не активен")

        response = SurveyResponse(
            survey_id=survey.id,
            respondent_id=respondent_id if not survey.is_anonymous else None,
            is_complete=False,
        )
        self._session.add(response)
        await self._session.flush()
        return response

    async def submit_response(
        self,
        survey: Survey,
        respondent_id: UUID | None,
        data: SubmitSurveyRequest,
        overwrite: bool = False,
    ) -> SurveyResponse:
        """Сохраняет ответы и завершает прохождение.

        При overwrite=True удаляет предыдущий ответ пользователя и записывает новый.
        """
        if survey.status != SurveyStatus.ACTIVE:
            raise ValueError("Опрос не активен")

        # Проверяем, не проходил ли уже (всегда, если известен respondent)
        if respondent_id:
            existing = await self._repo.get_by_respondent_and_survey(
                respondent_id, survey.id
            )
            if existing and existing.is_complete:
                if not overwrite:
                    raise ValueError("Вы уже прошли этот опрос")
                # Удаляем старый ответ перед записью нового
                await self._session.delete(existing)
                await self._session.flush()

        response = SurveyResponse(
            survey_id=survey.id,
            respondent_id=respondent_id,
            is_complete=True,
            submitted_at=datetime.now(timezone.utc),
        )
        self._session.add(response)
        await self._session.flush()

        # Сохраняем ответы на вопросы
        question_ids = {str(q.id) for q in survey.questions}
        for answer_data in data.answers:
            if str(answer_data.question_id) not in question_ids:
                continue
            answer = Answer(
                response_id=response.id,
                question_id=answer_data.question_id,
                text_value=answer_data.text_value,
                selected_options=[str(o) for o in answer_data.selected_options]
                if answer_data.selected_options
                else None,
            )
            self._session.add(answer)

        await self._session.flush()
        await self._session.refresh(response)
        return response

    async def get_survey_responses(self, survey_id: UUID) -> list[SurveyResponse]:
        return await self._repo.get_by_survey(survey_id)
