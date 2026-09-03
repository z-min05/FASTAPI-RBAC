import os

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.plan_repo import PlanRepository, PlanTestCaseRepository
from app.repositories.testcase_repo import TestCaseRepository
from app.repositories.project_repo import ProjectRepository
from app.models.plan import TestPlan
from app.models.plan_testcase import PlanTestCase
from app.models.testcase import TestCase
from app.models.project import Project
from app.models.user import User
from app.schemas.plan import (
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    PlanTestCaseResponse,
    ALLOWED_PLAN_STATUS,
    ALLOWED_RESULTS,
)
from app.core.pagination import PaginationParams, PaginatedResponse
from app.exceptions import NotFoundException, BadRequestException
from app.services.auto_exec_service import execute_testcase_background
from app.db.session import AsyncSessionLocal


def _empty_stats() -> dict:
    return {"pass": 0, "fail": 0, "blocked": 0, "skipped": 0, "pending": 0}


class PlanService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.plan_repo = PlanRepository(db)
        self.pt_repo = PlanTestCaseRepository(db)
        self.project_repo = ProjectRepository(db)
        self.testcase_repo = TestCaseRepository(db)

    # ---------- 计划查询 ----------

    async def get_plan(self, plan_id: int) -> TestPlan:
        plan = await self.plan_repo.get_by_id(plan_id)
        if not plan:
            raise NotFoundException("测试计划不存在")
        return plan

    async def get_plans(
        self,
        params: PaginationParams,
        project_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
        order: str = "desc",
    ) -> PaginatedResponse:
        filters = []
        if project_id is not None:
            filters.append(TestPlan.project_id == project_id)
        if status:
            filters.append(TestPlan.status == status)
        if keyword:
            filters.append(
                or_(
                    TestPlan.name.ilike(f"%{keyword}%"),
                    TestPlan.description.ilike(f"%{keyword}%"),
                )
            )
        result = await self.plan_repo.get_paginated(params, filters or None, order)
        stats = await self.pt_repo.stats_by_plans([p.id for p in result.items])
        project_map = await self._get_project_map([p.project_id for p in result.items])
        items = [
            self._to_plan_response(p, project_map, stats.get(p.id))
            for p in result.items
        ]
        return PaginatedResponse(
            items=items,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )

    async def get_plan_detail(self, plan_id: int) -> dict:
        plan = await self.get_plan(plan_id)
        stats = await self.pt_repo.stats_by_plans([plan.id])
        project_map = await self._get_project_map([plan.project_id])
        return self._to_plan_response(plan, project_map, stats.get(plan.id))

    async def _get_project_map(self, project_ids: list[int]) -> dict[int, Project]:
        ids = list(set(project_ids))
        if not ids:
            return {}
        stmt = select(Project).where(Project.id.in_(ids))
        result = await self.db.execute(stmt)
        return {p.id: p for p in result.scalars().all()}

    def _to_plan_response(
        self, plan: TestPlan, project_map: dict[int, Project], stats: dict | None
    ) -> dict:
        proj = project_map.get(plan.project_id)
        stat = stats or {"case_count": 0, "result_stats": _empty_stats()}
        return PlanResponse(
            id=plan.id,
            project_id=plan.project_id,
            project_code=proj.code if proj else None,
            project_name=proj.name if proj else None,
            name=plan.name,
            description=plan.description,
            status=plan.status,
            case_count=stat["case_count"],
            result_stats=stat["result_stats"],
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        ).model_dump()

    # ---------- 计划写操作 ----------

    async def _ensure_project_active(self, project_id: int) -> Project:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise BadRequestException("项目不存在")
        if not project.is_active:
            raise BadRequestException("项目已停用，不能在该项目下创建/操作测试计划")
        return project

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in ALLOWED_PLAN_STATUS:
            raise BadRequestException(f"计划状态不合法，应为: {', '.join(ALLOWED_PLAN_STATUS)}")

    async def create_plan(self, data: PlanCreate) -> TestPlan:
        await self._ensure_project_active(data.project_id)
        self._validate_status(data.status)
        plan = TestPlan(**data.model_dump())
        return await self.plan_repo.create(plan)

    async def update_plan(self, plan_id: int, data: PlanUpdate) -> TestPlan:
        plan = await self.get_plan(plan_id)
        update_data = data.model_dump(exclude_unset=True)
        if "status" in update_data:
            self._validate_status(update_data["status"])
        # 所属项目不可变更：直接忽略 project_id（schema 亦不含该字段）
        updated = await self.plan_repo.update(plan.id, update_data)
        return updated

    async def delete_plan(self, plan_id: int) -> None:
        plan = await self.get_plan(plan_id)
        # 关联的计划用例由数据库 ON DELETE CASCADE 一并清理
        await self.plan_repo.delete(plan.id)

    # ---------- 计划用例 ----------

    async def list_plan_testcases(
        self,
        params: PaginationParams,
        plan_id: int,
        keyword: str | None = None,
        result: str | None = None,
        tester_id: int | None = None,
    ) -> PaginatedResponse:
        await self.get_plan(plan_id)
        result_page = await self.pt_repo.search_by_plan(
            params, plan_id, keyword, result, tester_id
        )
        items = result_page.items
        tc_map = await self._get_testcase_map([pt.testcase_id for pt in items])
        user_map = await self._get_user_map([pt.tester_id for pt in items if pt.tester_id])
        rows = [
            self._to_pt_response(pt, tc_map, user_map)
            for pt in items
        ]
        return PaginatedResponse(
            items=rows,
            total=result_page.total,
            page=result_page.page,
            page_size=result_page.page_size,
            total_pages=result_page.total_pages,
        )

    async def get_candidates(
        self,
        params: PaginationParams,
        plan_id: int,
        keyword: str | None = None,
    ) -> PaginatedResponse:
        """候选用例：计划所属项目下、尚未加入该计划的用例"""
        plan = await self.get_plan(plan_id)
        exclude = await self.pt_repo.get_existing_testcase_ids(plan.id)
        filters = [TestCase.project_id == plan.project_id]
        if exclude:
            filters.append(TestCase.id.notin_(exclude))
        if keyword:
            filters.append(
                or_(
                    TestCase.title.ilike(f"%{keyword}%"),
                    TestCase.module.ilike(f"%{keyword}%"),
                )
            )
        page = await self.testcase_repo.get_paginated(params, filters or None, "desc")
        items = [
            {
                "id": tc.id,
                "title": tc.title,
                "module": tc.module,
                "priority": tc.priority,
                "case_type": tc.case_type,
                "source": tc.source,
                "status": tc.status,
            }
            for tc in page.items
        ]
        return PaginatedResponse(
            items=items,
            total=page.total,
            page=page.page,
            page_size=page.page_size,
            total_pages=page.total_pages,
        )

    async def add_testcases(self, plan_id: int, testcase_ids: list[int]) -> dict:
        """批量添加用例：仅限计划所属项目下的用例；已在计划中的自动跳过"""
        plan = await self.get_plan(plan_id)
        ids = list(dict.fromkeys(testcase_ids))
        if not ids:
            raise BadRequestException("请选择要添加的用例")

        stmt = select(TestCase).where(TestCase.id.in_(ids))
        testcases = list((await self.db.execute(stmt)).scalars().all())
        if len(testcases) != len(ids):
            found = {tc.id for tc in testcases}
            missing = [i for i in ids if i not in found]
            raise BadRequestException(f"部分用例不存在: {missing}")

        wrong = [tc.id for tc in testcases if tc.project_id != plan.project_id]
        if wrong:
            raise BadRequestException("只能添加该计划所属项目下的用例")

        existing = await self.pt_repo.get_existing_testcase_ids(plan.id)
        new_ids = [tc.id for tc in testcases if tc.id not in existing]
        for tid in new_ids:
            self.db.add(PlanTestCase(plan_id=plan.id, testcase_id=tid))
        await self.db.flush()
        return {"added": len(new_ids), "skipped": len(ids) - len(new_ids)}

    async def update_result(
        self,
        plan_id: int,
        ptc_id: int,
        result: str | None,
        result_desc: str | None,
        tester_id: int | None,
        current_user: User,
    ) -> PlanTestCase:
        """记录/修改测试结果；tester_id 缺省时回填当前用户（已有测试人则保留）"""
        plan = await self.get_plan(plan_id)
        pt = await self.pt_repo.get_by_id(ptc_id)
        if not pt or pt.plan_id != plan.id:
            raise NotFoundException("计划用例不存在")

        updates: dict = {}
        if result is not None:
            if result not in ALLOWED_RESULTS:
                raise BadRequestException(f"测试结果不合法，应为: {', '.join(ALLOWED_RESULTS)}")
            updates["result"] = result
        if result_desc is not None:
            updates["result_desc"] = result_desc
        new_tester = tester_id if tester_id is not None else (pt.tester_id or current_user.id)
        updates["tester_id"] = new_tester
        updated = await self.pt_repo.update(pt.id, updates)
        return updated

    async def remove_testcase(self, plan_id: int, ptc_id: int) -> None:
        plan = await self.get_plan(plan_id)
        pt = await self.pt_repo.get_by_id(ptc_id)
        if not pt or pt.plan_id != plan.id:
            raise NotFoundException("计划用例不存在")
        await self.pt_repo.delete(pt.id)

    # ---------- 自动化执行 ----------

    async def execute_auto_case(
        self,
        plan_id: int,
        ptc_id: int,
        current_user: User,
    ) -> None:
        """触发自动化执行：检查自动化字段都齐了 -> 设置 result=running -> 后台异步执行 pytest"""
        plan = await self.get_plan(plan_id)
        pt = await self.pt_repo.get_by_id(ptc_id)
        if not pt or pt.plan_id != plan.id:
            raise NotFoundException("计划用例不存在")

        tc = await self.testcase_repo.get_by_id(pt.testcase_id)
        if not tc:
            raise NotFoundException("关联用例不存在")

        # 检查自动化配置是否完整
        if not tc.module_code or not tc.case_code:
            raise BadRequestException("该用例未配置模块编码或用例编码，无法自动化执行")

        project = await self.project_repo.get_by_id(plan.project_id)
        if not project:
            raise NotFoundException("所属项目不存在")
        if not project.auto_root_path:
           raise BadRequestException("所属项目未配置自动化根路径，无法自动化执行")
        if not project.python_path:
            raise BadRequestException("所属项目未配置 Python 解释器路径，无法自动化执行")

        test_file = os.path.join(project.auto_root_path, f"{tc.module_code}.py")
        python_path = project.python_path

        # 设置为 running，后台执行
        await self.pt_repo.update(pt.id, {"result": "running", "result_desc": "正在执行中...", "tester_id": current_user.id})
        await self.db.commit()

        # 启动后台异步任务
        import asyncio
        task = asyncio.create_task(
            execute_testcase_background(
                AsyncSessionLocal,
                plan_id,
                ptc_id,
                python_path,
                test_file,
                tc.case_code,
                project.auto_root_path,
                current_user.id,
            )
        )

        # 保持强引用避免被 GC 回收
        from app.services.auto_exec_service import _running_tasks
        _running_tasks.add(task)
        def done_callback(t):
            _running_tasks.discard(t)
        task.add_done_callback(done_callback)

    async def execute_auto_cases(
        self,
        plan_id: int,
        ptc_ids: list[int],
        current_user: User,
    ) -> None:
        """批量串行执行自动化用例：全部设为 running -> 启动一个后台任务串行执行"""
        plan = await self.get_plan(plan_id)
        project = await self.project_repo.get_by_id(plan.project_id)
        if not project:
            raise NotFoundException("所属项目不存在")
        if not project.auto_root_path:
            raise BadRequestException("所属项目未配置自动化根路径，无法自动化执行")
        if not project.python_path:
            raise BadRequestException("所属项目未配置 Python 解释器路径，无法自动化执行")

        python_path = project.python_path
        entries: list[tuple[int, int, str, str]] = []  # (ptc_id, testcase_id, test_file, case_code)

        for ptc_id in ptc_ids:
            pt = await self.pt_repo.get_by_id(ptc_id)
            if not pt or pt.plan_id != plan.id:
                raise BadRequestException(f"计划用例 {ptc_id} 不存在")
            tc = await self.testcase_repo.get_by_id(pt.testcase_id)
            if not tc:
                raise BadRequestException(f"关联用例不存在 (ptc_id={ptc_id})")
            if not tc.module_code or not tc.case_code:
                raise BadRequestException(f"用例「{tc.title}」未配置模块编码或用例编码")
            test_file = os.path.join(project.auto_root_path, f"{tc.module_code}.py")
            entries.append((ptc_id, tc.id, test_file, tc.case_code))

        # 全部设为 running
        for ptc_id, _, _, _ in entries:
            await self.pt_repo.update(ptc_id, {"result": "running", "result_desc": "正在执行中..."})
        await self.db.commit()

        # 启动一个后台任务串行执行
        import asyncio
        from app.services.auto_exec_service import _execute_cases_sequential, _running_tasks
        task = asyncio.create_task(
            _execute_cases_sequential(
                AsyncSessionLocal,
                plan_id,
                entries,
                python_path,
                project.auto_root_path,
                current_user.id,
            )
        )
        _running_tasks.add(task)
        def done_callback(t):
            _running_tasks.discard(t)
        task.add_done_callback(done_callback)

    async def stop_execution(self, plan_id: int) -> None:
        """停止指定计划的批量执行"""
        from app.services.auto_exec_service import _stop_batch_flags
        _stop_batch_flags[plan_id] = True

    # ---------- 响应组装辅助 ----------

    async def _get_testcase_map(self, testcase_ids: list[int]) -> dict[int, TestCase]:
        ids = list(set(testcase_ids))
        if not ids:
            return {}
        stmt = select(TestCase).where(TestCase.id.in_(ids))
        result = await self.db.execute(stmt)
        return {tc.id: tc for tc in result.scalars().all()}

    async def _get_user_map(self, user_ids: list[int]) -> dict[int, User]:
        ids = list(set(user_ids))
        if not ids:
            return {}
        stmt = select(User).where(User.id.in_(ids))
        result = await self.db.execute(stmt)
        return {u.id: u for u in result.scalars().all()}

    def _to_pt_response(
        self,
        pt: PlanTestCase,
        tc_map: dict[int, TestCase],
        user_map: dict[int, User],
    ) -> dict:
        tc = tc_map.get(pt.testcase_id)
        user = user_map.get(pt.tester_id) if pt.tester_id else None
        return PlanTestCaseResponse(
            id=pt.id,
            plan_id=pt.plan_id,
            testcase_id=pt.testcase_id,
            title=tc.title if tc else None,
            module=tc.module if tc else None,
            priority=tc.priority if tc else None,
            case_type=tc.case_type if tc else None,
            source=tc.source if tc else None,
            status=tc.status if tc else None,
            precondition=tc.precondition if tc else None,
            steps=tc.steps if tc else None,
            expected_result=tc.expected_result if tc else None,
            tester_id=pt.tester_id,
            tester_name=(user.nickname or user.username) if user else None,
            result=pt.result,
            result_desc=pt.result_desc,
            module_code=tc.module_code if tc else None,
            case_code=tc.case_code if tc else None,
            created_at=pt.created_at,
            updated_at=pt.updated_at,
        ).model_dump()

    # ---------- 测试人下拉 ----------

    async def get_tester_candidates(self) -> list[dict]:
        """可选测试人：启用中的系统用户（下拉用）"""
        stmt = (
            select(User)
            .where(User.is_active.is_(True))
            .order_by(User.id)
        )
        result = await self.db.execute(stmt)
        return [
            {"id": u.id, "username": u.username, "nickname": u.nickname or u.username}
            for u in result.scalars().all()
        ]
