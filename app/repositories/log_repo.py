from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.operation_log import OperationLog
from app.repositories.base import BaseRepository


class LogRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(OperationLog, db)

    async def get_by_user_id(self, user_id: int) -> list[OperationLog]:
        stmt = select(OperationLog).where(OperationLog.user_id == user_id).order_by(OperationLog.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
