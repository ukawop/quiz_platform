"""Зависимости FastAPI (Dependency Injection)."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.llm.factory import get_llm_client
from app.llm.base import BaseLLMClient
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.repositories.survey_repository import SurveyRepository


async def get_user_by_header(
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_provider: Annotated[str, Header()] = "vk",
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Получает пользователя по заголовку X-User-Id.

    VK Bot передаёт vk_id пользователя в заголовке.
    Возвращает None если заголовок не передан (публичный доступ).
    """
    if not x_user_id:
        return None
    repo = UserRepository(session)
    user = await repo.get_by_external_id(x_user_id, x_user_provider)
    return user


async def require_user(
    user: Annotated[User | None, Depends(get_user_by_header)],
) -> User:
    """Требует аутентифицированного пользователя."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация. Передайте заголовок X-User-Id.",
        )
    return user


async def require_admin(
    user: Annotated[User, Depends(require_user)],
) -> User:
    """Требует роль ADMIN или SUPERADMIN."""
    if user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешён только администраторам.",
        )
    return user


async def require_superadmin(
    user: Annotated[User, Depends(require_user)],
) -> User:
    """Требует роль SUPERADMIN (главный администратор)."""
    if user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешён только главному администратору.",
        )
    return user


async def get_survey_or_404(
    survey_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    repo = SurveyRepository(session)
    survey = await repo.get_by_id_with_questions(survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    return survey


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_user)]
AdminUser = Annotated[User, Depends(require_admin)]
SuperAdminUser = Annotated[User, Depends(require_superadmin)]
OptionalUser = Annotated[User | None, Depends(get_user_by_header)]
LLMClient = Annotated[BaseLLMClient, Depends(get_llm_client)]
