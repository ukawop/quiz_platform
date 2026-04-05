from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, AdminUser, CurrentUser
from app.schemas.survey import SurveyCreate, SurveyRead, SurveyShort, SurveyWithStats
from app.services.survey_service import SurveyService

router = APIRouter(prefix="/surveys", tags=["surveys"])


@router.post("/", response_model=SurveyRead, status_code=status.HTTP_201_CREATED)
async def create_survey(
    data: SurveyCreate,
    session: DbSession,
    user: CurrentUser,
):
    """Создать новый опрос (любой авторизованный пользователь)."""
    service = SurveyService(session)
    survey = await service.create_survey(author=user, data=data)
    return survey


@router.get("/", response_model=list[SurveyShort])
async def list_my_surveys(session: DbSession, user: CurrentUser):
    """Список опросов текущего пользователя (автора)."""
    service = SurveyService(session)
    surveys = await service.get_author_surveys(user.id)
    result = []
    for s in surveys:
        result.append(
            SurveyShort(
                id=s.id,
                title=s.title,
                status=s.status,
                is_anonymous=s.is_anonymous,
                created_at=s.created_at,
                question_count=len(s.questions),
            )
        )
    return result


@router.get("/active", response_model=list[SurveyShort])
async def list_active_surveys(session: DbSession):
    """Список активных опросов (публичный)."""
    service = SurveyService(session)
    surveys = await service.get_active_surveys()
    return [
        SurveyShort(
            id=s.id,
            title=s.title,
            status=s.status,
            is_anonymous=s.is_anonymous,
            created_at=s.created_at,
            question_count=len(s.questions),
        )
        for s in surveys
    ]


@router.get("/all", response_model=list[SurveyWithStats])
async def list_all_surveys(session: DbSession, _admin: AdminUser):
    """Все опросы со статистикой (только для администраторов)."""
    service = SurveyService(session)
    rows = await service.get_dashboard_stats()
    return [
        SurveyWithStats(
            survey=SurveyShort(
                id=row["survey"].id,
                title=row["survey"].title,
                status=row["survey"].status,
                is_anonymous=row["survey"].is_anonymous,
                created_at=row["survey"].created_at,
                question_count=len(row["survey"].questions),
            ),
            response_count=row["response_count"],
        )
        for row in rows
    ]


@router.get("/dashboard", response_model=list[SurveyWithStats])
async def get_dashboard(session: DbSession, _admin: AdminUser):
    """Панель администратора: все опросы со статистикой."""
    service = SurveyService(session)
    rows = await service.get_dashboard_stats()
    return [
        SurveyWithStats(
            survey=SurveyShort(
                id=row["survey"].id,
                title=row["survey"].title,
                status=row["survey"].status,
                is_anonymous=row["survey"].is_anonymous,
                created_at=row["survey"].created_at,
                question_count=len(row["survey"].questions),
            ),
            response_count=row["response_count"],
        )
        for row in rows
    ]


@router.get("/{survey_id}", response_model=SurveyRead)
async def get_survey(survey_id: UUID, session: DbSession):
    """Получить опрос с вопросами (публичный)."""
    service = SurveyService(session)
    survey = await service.get_survey(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    return survey


@router.post("/{survey_id}/publish", response_model=SurveyRead)
async def publish_survey(survey_id: UUID, session: DbSession, user: CurrentUser):
    """Опубликовать опрос (автор или администратор)."""
    service = SurveyService(session)
    survey = await service.get_survey(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    return await service.publish_survey(survey)


@router.post("/{survey_id}/close", response_model=SurveyRead)
async def close_survey(survey_id: UUID, session: DbSession, user: CurrentUser):
    """Закрыть опрос (автор или администратор)."""
    service = SurveyService(session)
    survey = await service.get_survey(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    return await service.close_survey(survey)


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_survey(survey_id: UUID, session: DbSession, _admin: AdminUser):
    """Удалить опрос (только администратор)."""
    service = SurveyService(session)
    survey = await service.get_survey(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    await service.delete_survey(survey)
