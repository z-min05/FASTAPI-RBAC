from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
from app.models.testcase import TestCase
from app.repositories.base import BaseRepository
from app.core.pagination import PaginationParams, PaginatedResponse


class ProjectRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(Project, db)

    async def get_paginated(
        self,
        params: PaginationParams,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> PaginatedResponse:
        filters = []
        if keyword:
            filters.append(
                or_(
                    Project.name.ilike(f"%{keyword}%"),
                    Project.code.ilike(f"%{keyword}%"),
                )
            )
        if is_active is not None:
            filters.append(Project.is_active == is_active)
        return await super().get_paginated(params, filters or None)

    async def get_by_code(self, code: str) -> Project | None:
        stmt = select(Project).where(Project.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_all(self) -> list[Project]:
        stmt = select(Project).where(Project.is_active.is_(True)).order_by(Project.id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_testcases(self, project_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(TestCase)
            .where(TestCase.project_id == project_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
