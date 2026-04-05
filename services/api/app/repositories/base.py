from typing import Generic, TypeVar, Type, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Базовый репозиторий с CRUD-операциями."""

    def __init__(self, model: Type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, obj_id: UUID) -> ModelT | None:
        return await self.session.get(self.model, obj_id)

    async def get_all(self, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()
