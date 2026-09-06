from sqlalchemy import select, func, or_, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.plan import TestPlan
from app.models.plan_testcase import PlanTestCase
from app.models.testcase import TestCase
from app.repositories.base import BaseRepository
from app.core.pagination import PaginationParams, PaginatedResponse

# 结果统计 key 顺序（与 schema 保持一致，pending 表示未回填结果）
RESULT_STAT_KEYS = ["pass", "fail", "blocked", "skipped", "pending"]


class PlanRepository(BaseRepository):
    """测试计划数据访问（模型 TestPlan，表 plans）"""

    def __init__(self, db: AsyncSession):
        super().__init__(TestPlan, db)

    async def get_paginated(
        self,
        params: PaginationParams,
        filters: list | None = None,
        order: str = "desc",
    ) -> PaginatedResponse:
        # 按创建时间排序（默认倒序：最新创建在前），id 作为稳定次序
        created_col = desc if order == "desc" else asc
        id_col = desc if order == "desc" else asc
        order_by = [created_col(TestPlan.created_at), id_col(TestPlan.id)]
        return await super().get_paginated(params, filters, order_by=order_by)

    async def count_by_project(self, project_id: int) -> int:
        """删除项目前的引用保护：该项目下的计划数"""
        stmt = select(func.count()).select_from(TestPlan).where(TestPlan.project_id == project_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0


class PlanTestCaseRepository(BaseRepository):
    """计划用例（plan_testcases 关联表）数据访问"""

    def __init__(self, db: AsyncSession):
        super().__init__(PlanTestCase, db)

    async def get_by_plan(self, plan_id: int) -> list[PlanTestCase]:
        """计划内全部关联（按添加时间正序）"""
        stmt = (
            select(PlanTestCase)
            .where(PlanTestCase.plan_id == plan_id)
            .order_by(PlanTestCase.id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_existing_testcase_ids(self, plan_id: int) -> set[int]:
        """计划内已关联的用例 ID 集合（用于添加时去重）"""
        stmt = select(PlanTestCase.testcase_id).where(PlanTestCase.plan_id == plan_id)
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def search_by_plan(
        self,
        params: PaginationParams,
        plan_id: int,
        keyword: str | None = None,
        result: str | None = None,
        tester_id: int | None = None,
    ) -> PaginatedResponse:
        """计划用例分页列表（联查用例标题/模块做筛选），按添加时间正序"""
        filters = [PlanTestCase.plan_id == plan_id]
        join_cond = [PlanTestCase.testcase_id == TestCase.id]
        if keyword:
            filters.append(
                or_(
                    TestCase.title.ilike(f"%{keyword}%"),
                    TestCase.module.ilike(f"%{keyword}%"),
                )
            )
        if result:
            filters.append(PlanTestCase.result == result)
        if tester_id is not None:
            filters.append(PlanTestCase.tester_id == tester_id)

        count_stmt = (
            select(func.count())
            .select_from(PlanTestCase)
            .join(TestCase, *join_cond)
            .where(*filters)
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(PlanTestCase)
            .join(TestCase, *join_cond)
            .where(*filters)
            .order_by(PlanTestCase.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        total_pages = (total + params.page_size - 1) // params.page_size if total > 0 else 0
        return PaginatedResponse(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages,
        )

    async def count_by_testcase(self, testcase_id: int) -> int:
        """删除用例前的引用保护：该用例被多少计划引用"""
        stmt = (
            select(func.count())
            .select_from(PlanTestCase)
            .where(PlanTestCase.testcase_id == testcase_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def count_by_testcases(self, testcase_ids: list[int]) -> int:
        """批量删除用例前的引用保护"""
        if not testcase_ids:
            return 0
        stmt = (
            select(func.count())
            .select_from(PlanTestCase)
            .where(PlanTestCase.testcase_id.in_(testcase_ids))
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def stats_by_plans(self, plan_ids: list[int]) -> dict[int, dict]:
        """批量统计各计划的用例数与结果分布 {plan_id: {case_count, result_stats}}"""
        result: dict[int, dict] = {}
        ids = list(dict.fromkeys(plan_ids))
        if not ids:
            return result
        for pid in ids:
            result[pid] = {"case_count": 0, "result_stats": {k: 0 for k in RESULT_STAT_KEYS}}

        count_stmt = (
            select(PlanTestCase.plan_id, func.count())
            .where(PlanTestCase.plan_id.in_(ids))
            .group_by(PlanTestCase.plan_id)
        )
        for pid, cnt in (await self.db.execute(count_stmt)).all():
            result[pid]["case_count"] = cnt

        group_stmt = (
            select(PlanTestCase.plan_id, PlanTestCase.result, func.count())
            .where(PlanTestCase.plan_id.in_(ids), PlanTestCase.result.isnot(None))
            .group_by(PlanTestCase.plan_id, PlanTestCase.result)
        )
        done: dict[int, int] = {}
        for pid, res, cnt in (await self.db.execute(group_stmt)).all():
            result[pid]["result_stats"][res] = cnt
            done[pid] = done.get(pid, 0) + cnt

        for pid, stat in result.items():
            stat["result_stats"]["pending"] = max(0, stat["case_count"] - done.get(pid, 0))
        return result
