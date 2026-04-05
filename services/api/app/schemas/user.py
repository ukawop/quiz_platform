from uuid import UUID
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class UserRead(BaseModel):
    id: UUID
    external_id: str
    external_provider: str
    display_name: str | None
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpsert(BaseModel):
    """Создание или обновление пользователя через внешний провайдер."""
    external_id: str
    external_provider: str = "vk"
    display_name: str | None = None
    role: UserRole = UserRole.USER
