from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, AdminUser, OptionalUser
from app.repositories.survey_repository import SurveyRepository
from app.repositories.response_repository import ResponseRepository
from app.schemas.response import SubmitSurveyRequest, SurveyResponseRead
from app.services.response_service import ResponseService

router = APIRouter(prefix="/surveys/{survey_id}/responses", tags=["responses"])


@router.post("/", response_model=SurveyResponseRead, status_code=status.HTTP_201_CREATED)
async def submit_response(
    survey_id: UUID,
    data: SubmitSurveyRequest,
    session: DbSession,
    current_user: OptionalUser,
    overwrite: bool = Query(False, description="Перезаписать предыдущий ответ"),
):
    """Отправить ответы на опрос.

    Доступно всем (пользователь может быть анонимным).
    Если опрос не анонимный — требуется заголовок X-User-Id.
    При overwrite=true — предыдущий ответ пользователя удаляется и записывается новый.
    """
    survey_repo = SurveyRepository(session)
    survey = await survey_repo.get_by_id_with_questions(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")

    if not survey.is_anonymous and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Этот опрос не анонимный. Передайте заголовок X-User-Id.",
        )

    service = ResponseService(session)
    try:
        response = await service.submit_response(
            survey=survey,
            respondent_id=current_user.id if current_user else None,
            data=data,
            overwrite=overwrite,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return response


@router.get("/my", response_model=SurveyResponseRead | None)
async def get_my_response(
    survey_id: UUID,
    session: DbSession,
    current_user: OptionalUser,
):
    """Получить свой ответ на опрос (None если не проходил).

    Используется ботом для пометки пройденных опросов.
    """
    if not current_user:
        return None
    repo = ResponseRepository(session)
    return await repo.get_by_respondent_and_survey(current_user.id, survey_id)


@router.get("/", response_model=list[SurveyResponseRead])
async def list_responses(
    survey_id: UUID,
    session: DbSession,
    _admin: AdminUser,
):
    """Список всех ответов по опросу (только для администраторов)."""
    service = ResponseService(session)
    return await service.get_survey_responses(survey_id)
