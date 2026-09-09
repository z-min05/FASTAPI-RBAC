import os
from datetime import datetime

import csv
import io
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
from app.models.wecom_robot import WecomRobot
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
from app.dependency import actor_user_id
from app.services.auto_exec_service import execute_testcase_background
from app.models.case_execution_log import CaseExecutionLog
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
        robot_map = await self._get_robot_map(plan.robot_ids or [])
        return self._to_plan_response(plan, project_map, stats.get(plan.id), robot_map)

    async def _get_project_map(self, project_ids: list[int]) -> dict[int, Project]:
        ids = list(set(project_ids))
        if not ids:
            return {}
        stmt = select(Project).where(Project.id.in_(ids))
        result = await self.db.execute(stmt)
        return {p.id: p for p in result.scalars().all()}

    async def _validate_robot_ids(self, robot_ids: list[int] | None) -> None:
        """校验绑定的机器人 id 均存在（可绑定已停用机器人，保持历史推送目标）"""
        if not robot_ids:
            return
        ids = list(set(robot_ids))
        found = (
            (await self.db.execute(select(WecomRobot.id).where(WecomRobot.id.in_(ids))))
            .scalars()
            .all()
        )
        missing = set(ids) - set(found)
        if missing:
            raise BadRequestException(f"部分企业微信群机器人不存在: {sorted(missing)}")

    async def _get_robot_map(self, robot_ids) -> dict[int, str]:
        ids = list(set(robot_ids))
        if not ids:
            return {}
        rows = (await self.db.execute(select(WecomRobot.id, WecomRobot.name).where(WecomRobot.id.in_(ids)))).all()
        return {r.id: r.name for r in rows}

    def _to_plan_response(
        self,
        plan: TestPlan,
        project_map: dict[int, Project],
        stats: dict | None,
        robot_map: dict[int, str] | None = None,
    ) -> dict:
        proj = project_map.get(plan.project_id)
        stat = stats or {"case_count": 0, "result_stats": _empty_stats()}
        robot_map = robot_map or {}
        robots = [
            {"id": rid, "name": robot_map.get(rid, f"#{rid}")}
            for rid in (plan.robot_ids or [])
        ]
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
            robot_ids=plan.robot_ids,
            robots=robots,
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
        await self._validate_robot_ids(data.robot_ids)
        plan = TestPlan(**data.model_dump())
        return await self.plan_repo.create(plan)

    async def update_plan(self, plan_id: int, data: PlanUpdate) -> TestPlan:
        plan = await self.get_plan(plan_id)
        update_data = data.model_dump(exclude_unset=True)
        if "status" in update_data:
            self._validate_status(update_data["status"])
        if "robot_ids" in update_data:
            await self._validate_robot_ids(update_data["robot_ids"])
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
        current_user: User,
    ) -> PlanTestCase:
        """记录/修改测试结果，测试人直接设为当前用户"""
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
        updates["tester_id"] = current_user.id
        updated = await self.pt_repo.update(pt.id, updates)
        return updated

    async def remove_testcase(self, plan_id: int, ptc_id: int) -> None:
        plan = await self.get_plan(plan_id)
        pt = await self.pt_repo.get_by_id(ptc_id)
        if not pt or pt.plan_id != plan.id:
            raise NotFoundException("计划用例不存在")
        await self.pt_repo.delete(pt.id)

    # ---------- 用例执行日志 ----------

    async def _check_plan_testcase(self, plan_id: int, ptc_id: int) -> None:
        plan = await self.get_plan(plan_id)
        pt = await self.pt_repo.get_by_id(ptc_id)
        if not pt or pt.plan_id != plan.id:
            raise NotFoundException("计划用例不存在")

    async def list_case_execution_logs(self, plan_id: int, ptc_id: int) -> list[dict]:
        """该计划用例的历史执行日志，按时间倒序（最新在前）"""
        await self._check_plan_testcase(plan_id, ptc_id)
        stmt = (
            select(CaseExecutionLog)
            .where(
                CaseExecutionLog.plan_id == plan_id,
                CaseExecutionLog.plan_testcase_id == ptc_id,
            )
            .order_by(CaseExecutionLog.id.desc())
        )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        latest_id = rows[0].id if rows else None
        tester_ids = [r.tester_id for r in rows if r.tester_id]
        user_map = await self._get_user_map(tester_ids)
        return [
            {
                "id": r.id,
                "plan_id": r.plan_id,
                "plan_testcase_id": r.plan_testcase_id,
                "result": r.result,
                "log_content": r.log_content,
                "tester_id": r.tester_id,
                "tester_name": (
                    (user_map[r.tester_id].nickname or user_map[r.tester_id].username)
                    if r.tester_id and r.tester_id in user_map else None
                ),
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "created_at": r.created_at,
                "is_latest": r.id == latest_id,
            }
            for r in rows
        ]

    async def delete_case_execution_log(self, plan_id: int, ptc_id: int, log_id: int) -> None:
        """删除单条历史执行日志；最新一条不允许删除（需先产生新执行记录）"""
        await self._check_plan_testcase(plan_id, ptc_id)
        stmt = (
            select(CaseExecutionLog)
            .where(CaseExecutionLog.id == log_id)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if not row or row.plan_id != plan_id or row.plan_testcase_id != ptc_id:
            raise NotFoundException("执行日志不存在")

        # 校验不是该计划用例的最新一次执行
        latest_stmt = (
            select(CaseExecutionLog.id)
            .where(
                CaseExecutionLog.plan_id == plan_id,
                CaseExecutionLog.plan_testcase_id == ptc_id,
            )
            .order_by(CaseExecutionLog.id.desc())
            .limit(1)
        )
        latest_id = (await self.db.execute(latest_stmt)).scalar_one_or_none()
        if latest_id is not None and row.id == latest_id:
            raise BadRequestException("最新一次执行日志不允许删除")

        await self.db.delete(row)
        await self.db.commit()

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

        # 设置为 running，后台执行（操作人统一取 actor_user_id，兼容 API 密钥归属用户）
        actor_id = actor_user_id(current_user)
        await self.pt_repo.update(pt.id, {"result": "running", "result_desc": "正在执行中...", "tester_id": actor_id})
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
                actor_id,
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
        from app.services.wecom_service import notify_plan_finished
        actor_id = actor_user_id(current_user)
        started_at = datetime.now()
        task = asyncio.create_task(
            _execute_cases_sequential(
                AsyncSessionLocal,
                plan_id,
                entries,
                python_path,
                project.auto_root_path,
                actor_id,
            )
        )
        _running_tasks.add(task)

        def done_callback(t):
            _running_tasks.discard(t)
            if t.cancelled():
                return
            # 整轮结束（正常/被终止）后，向计划绑定的企业微信机器人推送统计（旁路）
            asyncio.create_task(
                notify_plan_finished(
                    plan_id,
                    "手动批量",
                    actor_id,
                    [e[0] for e in entries],
                    started_at,
                    datetime.now(),
                )
            )

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

    # ---------- 导出 ----------

    async def export_plan_testcases(self, plan_id: int) -> str:
        """导出计划用例为 CSV 文本（UTF-8 BOM）"""
        plan = await self.get_plan(plan_id)
        stmt = (
            select(PlanTestCase)
            .where(PlanTestCase.plan_id == plan.id)
            .order_by(PlanTestCase.id)
        )
        result = await self.db.execute(stmt)
        pts = list(result.scalars().all())
        tc_ids = [pt.testcase_id for pt in pts]
        user_ids = [pt.tester_id for pt in pts if pt.tester_id]
        tc_map = await self._get_testcase_map(tc_ids)
        user_map = await self._get_user_map(user_ids)

        buf = io.StringIO()
        buf.write("\ufeff")
        writer = csv.writer(buf)
        writer.writerow([
            "用例标题", "模块", "优先级", "用例类型",
            "前置条件", "测试步骤", "预期结果",
            "测试人", "结果", "结果描述",
        ])
        for pt in pts:
            tc = tc_map.get(pt.testcase_id)
            user = user_map.get(pt.tester_id) if pt.tester_id else None
            _result_label = {"pass": "通过", "fail": "失败", "blocked": "阻塞", "skipped": "跳过", "running": "执行中"}.get(pt.result or "", pt.result or "")
            writer.writerow([
                tc.title if tc else "",
                tc.module if tc else "",
                tc.priority if tc else "",
                tc.case_type if tc else "",
                tc.precondition or "",
                tc.steps or "",
                tc.expected_result if tc else "",
                (user.nickname or user.username) if user else "",
                _result_label,
                pt.result_desc or "",
            ])
        return buf.getvalue()
