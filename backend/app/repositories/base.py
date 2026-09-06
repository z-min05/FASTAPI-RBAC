from typing import TypeVar, Type, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.pagination import PaginationParams, PaginatedResponse, paginate

ModelType = TypeVar("ModelType")


class BaseRepository:
    """通用 CRUD 基类"""

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> list[ModelType]:
        stmt = select(self.model)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_paginated(self, params: PaginationParams, filters: list | None = None, options: list | None = None, order_by: list | None = None) -> PaginatedResponse:
        return await paginate(self.db, self.model, params, filters, options, order_by)

    async def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, id: int, data: dict[str, Any]) -> Optional[ModelType]:
        obj = await self.get_by_id(id)
        if obj is None:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True

    async def delete_batch(self, ids: list[int]) -> int:
        count = 0
        for id in ids:
            if await self.delete(id):
                count += 1
        return count
