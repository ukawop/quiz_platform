import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import DbSession, AdminUser, CurrentUser, LLMClient
from app.repositories.survey_repository import SurveyRepository
from app.schemas.analytics import AIAnalysisRead, SurveyStatsRead
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/surveys/{survey_id}/analytics", tags=["analytics"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.get("/stats", response_model=SurveyStatsRead)
async def get_survey_stats(
    survey_id: UUID,
    session: DbSession,
    _user: CurrentUser,
):
    """Базовая статистика по опросу: количество ответов, распределение по вариантам."""
    survey_repo = SurveyRepository(session)
    survey = await survey_repo.get_by_id_with_questions(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")

    service = AnalyticsService(session=session, llm_client=None)  # type: ignore[arg-type]
    stats = await service.get_survey_stats(survey_id)
    return stats


@router.post("/ai", response_model=AIAnalysisRead)
async def run_ai_analysis(
    survey_id: UUID,
    session: DbSession,
    _user: CurrentUser,
    llm: LLMClient,
):
    """Запустить AI-анализ открытых ответов по опросу.

    Анализирует только вопросы с флагом ai_analyze=True.
    Результат сохраняется в БД и возвращается.
    """
    survey_repo = SurveyRepository(session)
    survey = await survey_repo.get_by_id_with_questions(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")

    service = AnalyticsService(session=session, llm_client=llm)
    try:
        result = await service.run_ai_analysis(survey_id)
    except Exception as e:
        logger.exception("Ошибка AI-анализа для опроса %s: %s", survey_id, e)
        raise HTTPException(status_code=500, detail=f"Ошибка AI-анализа: {e}")
    return result


@router.get("/ai", response_model=AIAnalysisRead)
async def get_ai_analysis(
    survey_id: UUID,
    session: DbSession,
    _user: CurrentUser,
):
    """Получить сохранённый результат AI-анализа."""
    service = AnalyticsService(session=session, llm_client=None)  # type: ignore[arg-type]
    result = await service.get_analysis(survey_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="AI-анализ ещё не запускался. Используйте POST /ai для запуска.",
        )
    return result


@router.post("/ask", response_model=AskResponse)
async def ask_ai(
    survey_id: UUID,
    body: AskRequest,
    session: DbSession,
    _user: CurrentUser,
    llm: LLMClient,
):
    """Свободный вопрос к AI с контекстом опроса.

    AI получает: название опроса, все вопросы с вариантами ответов,
    ответы участников (до 50). Автор задаёт произвольный вопрос.
    """
    survey_repo = SurveyRepository(session)
    survey = await survey_repo.get_by_id_with_questions(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")

    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Вопрос не может быть пустым")

    service = AnalyticsService(session=session, llm_client=llm)
    try:
        answer = await service.ask_question(survey_id, body.question.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка AI: {e}")

    return AskResponse(answer=answer)
