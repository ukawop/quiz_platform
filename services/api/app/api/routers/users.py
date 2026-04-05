from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from app.api.deps import DbSession, AdminUser, SuperAdminUser, CurrentUser
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRead, UserUpsert

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/upsert", response_model=UserRead, status_code=status.HTTP_200_OK)
async def upsert_user(data: UserUpsert, session: DbSession):
    """Создать или обновить пользователя по внешнему ID."""
    repo = UserRepository(session)
    user, _ = await repo.get_or_create(
        external_id=data.external_id,
        provider=data.external_provider,
        display_name=data.display_name,
        role=data.role,
    )
    return user


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser):
    """Получить профиль текущего пользователя (требует X-User-Id заголовок)."""
    return current_user


@router.get("/admins", response_model=list[UserRead])
async def list_admins(session: DbSession, _admin: AdminUser):
    """Список всех администраторов (admin + superadmin). Доступно всем админам."""
    repo = UserRepository(session)
    return await repo.get_admins()


@router.post("/{external_id}/make-admin", response_model=UserRead)
async def make_admin(
    external_id: str,
    session: DbSession,
    _superadmin: SuperAdminUser,
    x_user_provider: Annotated[str, Header()] = "vk",
):
    """Назначить пользователя администратором. Только для суперадмина."""
    repo = UserRepository(session)
    user = await repo.get_by_external_id(external_id, x_user_provider)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.role == UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя изменить роль суперадмина.",
        )
    user.role = UserRole.ADMIN
    await session.flush()
    return user


@router.post("/{external_id}/make-user", response_model=UserRead)
async def make_user(
    external_id: str,
    session: DbSession,
    _superadmin: SuperAdminUser,
    x_user_provider: Annotated[str, Header()] = "vk",
):
    """Снять права администратора. Только для суперадмина."""
    repo = UserRepository(session)
    user = await repo.get_by_external_id(external_id, x_user_provider)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.role == UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя изменить роль суперадмина.",
        )
    user.role = UserRole.USER
    await session.flush()
    return user


@router.patch("/{external_id}/role", response_model=UserRead)
async def set_user_role(
    external_id: str,
    role: UserRole,
    session: DbSession,
    _superadmin: SuperAdminUser,
    x_user_provider: Annotated[str, Header()] = "vk",
):
    """Изменить роль пользователя. Только для суперадмина."""
    repo = UserRepository(session)
    user = await repo.get_by_external_id(external_id, x_user_provider)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.role == UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя изменить роль суперадмина.",
        )
    if role == UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя назначить роль суперадмина через API.",
        )
    user.role = role
    await session.flush()
    return user
