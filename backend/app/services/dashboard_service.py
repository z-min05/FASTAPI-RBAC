from datetime import datetime, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import TestPlan
from app.models.plan_testcase import PlanTestCase
from app.models.testcase import TestCase


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stats(self) -> dict:
        """获取仪表盘统计：测试管理相关数据"""
        # 1. 基础计数
        plan_count = await self._count(select(func.count(TestPlan.id)).select_from(TestPlan))
        case_count = await self._count(select(func.count(TestCase.id)).select_from(TestCase))
        # 已执行（有结果）的计划用例数
        executed_count = await self._count(
            select(func.count(PlanTestCase.id)).select_from(PlanTestCase)
            .where(PlanTestCase.result.isnot(None))
        )
        # 今日执行次数（数据库字段为 TIMESTAMP WITHOUT TIME ZONE，使用无时区 datetime）
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = await self._count(
            select(func.count(PlanTestCase.id)).select_from(PlanTestCase)
            .where(
                and_(
                    PlanTestCase.result.isnot(None),
                    PlanTestCase.updated_at >= today_start,
                )
            )
        )

        # 2. 各计划用例分布（取前10个计划）
        plan_dist = await self._plan_distribution()

        # 3. 测试结果分布
        result_dist = await self._result_distribution()

        # 4. 近7日执行趋势
        daily_trend = await self._daily_trend(days=7)

        # 5. 各模块用例统计（取前10个模块）
        module_dist = await self._module_distribution()

        return {
            "planCount": plan_count,
            "caseCount": case_count,
            "executedCount": executed_count,
            "todayCount": today_count,
            "planDistribution": plan_dist,
            "resultDistribution": result_dist,
            "dailyTrend": daily_trend,
            "moduleDistribution": module_dist,
        }

    async def _count(self, stmt) -> int:
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _plan_distribution(self) -> list:
        stmt = (
            select(TestPlan.name, func.count(PlanTestCase.id).label("cnt"))
            .outerjoin(PlanTestCase, PlanTestCase.plan_id == TestPlan.id)
            .group_by(TestPlan.id, TestPlan.name)
            .order_by(func.count(PlanTestCase.id).desc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        return [{"name": name, "value": cnt} for name, cnt in result]

    async def _result_distribution(self) -> list:
        stmt = (
            select(PlanTestCase.result, func.count(PlanTestCase.id).label("cnt"))
            .where(PlanTestCase.result.isnot(None))
            .group_by(PlanTestCase.result)
        )
        result = await self.db.execute(stmt)
        label_map = {
            "pass": "通过", "fail": "失败", "blocked": "阻塞",
            "skipped": "跳过", "running": "执行中",
        }
        return [
            {"name": label_map.get(res or "", res or ""), "value": cnt}
            for res, cnt in result
        ]

    async def _daily_trend(self, days: int) -> list:
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = end_date - timedelta(days=days - 1)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # 使用 PostgreSQL 的 date 函数按天分组
        stmt = (
            select(
                func.date(PlanTestCase.updated_at).label("day"),
                func.count(PlanTestCase.id).label("cnt"),
            )
            .where(
                and_(
                    PlanTestCase.result.isnot(None),
                    PlanTestCase.updated_at >= start_date,
                    PlanTestCase.updated_at <= end_date,
                )
            )
            .group_by(func.date(PlanTestCase.updated_at))
            .order_by(func.date(PlanTestCase.updated_at))
        )
        result = await self.db.execute(stmt)
        row_map = {str(day): cnt for day, cnt in result}

        # 补全所有日期
        trend = []
        for i in range(days):
            d = (start_date + timedelta(days=i)).strftime("%m-%d")
            cnt = row_map.get(
                (start_date + timedelta(days=i)).strftime("%Y-%m-%d"), 0
            )
            trend.append({"date": d, "count": cnt})
        return trend

    async def _module_distribution(self) -> list:
        stmt = (
            select(TestCase.module, func.count(TestCase.id).label("cnt"))
            .group_by(TestCase.module)
            .order_by(func.count(TestCase.id).desc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        return [{"name": module, "value": cnt} for module, cnt in result]