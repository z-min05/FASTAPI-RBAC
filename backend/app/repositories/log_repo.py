from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.operation_log import OperationLog
from app.repositories.base import BaseRepository
from app.core.pagination import PaginationParams, PaginatedResponse


class LogRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(OperationLog, db)

    async def get_paginated(
        self,
        params: PaginationParams,
        order: str = "desc",
    ) -> PaginatedResponse:
        # 按记录时间排序（默认倒序：最新在前），id 作为稳定次序
        col = desc if order == "desc" else asc
        order_by = [col(OperationLog.created_at), col(OperationLog.id)]
        return await super().get_paginated(params, order_by=order_by)

    async def get_by_user_id(self, user_id: int) -> list[OperationLog]:
        stmt = select(OperationLog).where(OperationLog.user_id == user_id).order_by(OperationLog.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
