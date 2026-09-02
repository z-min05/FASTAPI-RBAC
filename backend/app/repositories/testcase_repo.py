from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.testcase import TestCase
from app.repositories.base import BaseRepository
from app.core.pagination import PaginationParams, PaginatedResponse


class TestCaseRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(TestCase, db)

    async def get_paginated(
        self, params: PaginationParams, filters: list | None = None
    ) -> PaginatedResponse:
        return await super().get_paginated(params, filters)

    async def get_modules(self, project_id: int | None = None) -> list[str]:
        stmt = select(TestCase.module).distinct().order_by(TestCase.module)
        if project_id is not None:
            stmt = stmt.where(TestCase.project_id == project_id)
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]
