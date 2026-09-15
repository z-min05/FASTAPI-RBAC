from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.testcase import TestCase
from app.models.testcase_module import TestCaseModule
from app.repositories.base import BaseRepository


class TestCaseModuleRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(TestCaseModule, db)

    async def get_by_project(self, project_id: int) -> list[TestCaseModule]:
        """取项目下全部模块节点（同级按 sort、id 排序）"""
        stmt = (
            select(TestCaseModule)
            .where(TestCaseModule.project_id == project_id)
            .order_by(TestCaseModule.sort.asc(), TestCaseModule.id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_children(self, parent_id: int) -> int:
        stmt = select(func.count(TestCaseModule.id)).where(
            TestCaseModule.parent_id == parent_id
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def count_cases(self, module_id: int) -> int:
        stmt = select(func.count(TestCase.id)).where(TestCase.module_id == module_id)
        return (await self.db.execute(stmt)).scalar() or 0

    async def case_counts(self, module_ids: list[int]) -> dict[int, int]:
        """一次查出多个模块各自直接挂载的用例数"""
        if not module_ids:
            return {}
        stmt = (
            select(TestCase.module_id, func.count(TestCase.id))
            .where(TestCase.module_id.in_(module_ids))
            .group_by(TestCase.module_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    async def exists_sibling(
        self,
        project_id: int,
        parent_id: int | None,
        name: str | None = None,
        code: str | None = None,
        exclude_id: int | None = None,
    ) -> bool:
        """同级是否已存在同 name / 同 code 的节点

        注意：PostgreSQL 中 NULL 互不相等，这里对顶级节点显式用 IS NULL 比较，
        否则顶级重名无法被检出。
        """
        filters = [TestCaseModule.project_id == project_id]
        if parent_id is None:
            filters.append(TestCaseModule.parent_id.is_(None))
        else:
            filters.append(TestCaseModule.parent_id == parent_id)
        conditions = []
        if name is not None:
            conditions.append(TestCaseModule.name == name)
        if code is not None:
            conditions.append(TestCaseModule.code == code)
        if not conditions:
            return False
        filters.append(or_(*conditions))
        if exclude_id is not None:
            filters.append(TestCaseModule.id != exclude_id)
        stmt = select(TestCaseModule.id).where(*filters).limit(1)
        return (await self.db.execute(stmt)).scalar() is not None
