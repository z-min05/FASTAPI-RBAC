from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.department import Department
from app.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(Department, db)

    async def get_by_parent_id(self, parent_id: int | None) -> list[Department]:
        stmt = select(Department).where(Department.parent_id == parent_id).order_by(Department.sort)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_departments(self) -> list[Department]:
        stmt = select(Department).order_by(Department.sort)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
