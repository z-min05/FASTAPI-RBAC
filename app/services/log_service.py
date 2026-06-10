from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.log_repo import LogRepository
from app.models.operation_log import OperationLog
from app.core.pagination import PaginationParams, PaginatedResponse


class LogService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.log_repo = LogRepository(db)

    async def get_logs(self, params: PaginationParams) -> PaginatedResponse:
        return await self.log_repo.get_paginated(params)

    async def get_user_logs(self, user_id: int) -> list[OperationLog]:
        return await self.log_repo.get_by_user_id(user_id)

    async def create_log(self, log_data: dict) -> OperationLog:
        log = OperationLog(**log_data)
        return await self.log_repo.create(log)
