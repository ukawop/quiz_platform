from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_external_id(self, external_id: str, provider: str = "vk") -> User | None:
        result = await self.session.execute(
            select(User).where(
                User.external_id == external_id,
                User.external_provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        external_id: str,
        provider: str = "vk",
        display_name: str | None = None,
        role: UserRole = UserRole.USER,
    ) -> tuple[User, bool]:
        """Возвращает (user, created). created=True если пользователь создан.

        Роль повышается если новая роль выше текущей (superadmin > admin > user).
        Никогда не понижается автоматически.
        """
        _role_priority = {UserRole.USER: 0, UserRole.ADMIN: 1, UserRole.SUPERADMIN: 2}
        user = await self.get_by_external_id(external_id, provider)
        if user:
            if display_name and user.display_name != display_name:
                user.display_name = display_name
            if _role_priority.get(role, 0) > _role_priority.get(user.role, 0):
                user.role = role
            await self.session.flush()
            return user, False
        user = User(
            external_id=external_id,
            external_provider=provider,
            display_name=display_name,
            role=role,
        )
        user = await self.create(user)
        return user, True

    async def get_admins(self) -> list[User]:
        """Возвращает всех пользователей с ролью admin или superadmin."""
        result = await self.session.execute(
            select(User).where(
                User.role.in_([UserRole.ADMIN, UserRole.SUPERADMIN])
            ).order_by(User.created_at)
        )
        return list(result.scalars().all())
