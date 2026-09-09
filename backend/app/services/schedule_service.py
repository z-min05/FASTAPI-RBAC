"""定时执行服务

职责：
- 定时任务 CRUD（cron 校验、计算下次运行时间、执行范围校验）
- 认领并触发一轮执行（DB 条件更新防重复；多 worker/多进程下安全）
- 执行编排：复用 auto_exec_service._execute_cases_sequential 批量执行内核

约定：
- 时间一律使用 offset-naive 本地时间（datetime.now()），与全库一致
- 不建独立"运行历史表"，最近一次状态记录在任务行上
"""
import asyncio
import os
from datetime import datetime, timedelta

from croniter import croniter
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.exceptions import BadRequestException, NotFoundException
from app.models.plan import TestPlan
from app.models.plan_schedule import PlanSchedule
from app.models.plan_testcase import PlanTestCase
from app.models.project import Project
from app.models.testcase import TestCase
from app.schemas.plan import (
    ALLOWED_SCHEDULE_MODES,
    PlanScheduleCreate,
    PlanScheduleResponse,
    PlanScheduleUpdate,
)
from app.services.auto_exec_service import _execute_cases_sequential, _running_tasks
from app.utils.logger import logger


# ---------- cron 工具 ----------

def _validate_cron(cron_expr: str) -> None:
    """校验 cron 表达式合法性"""
    if not croniter.is_valid(cron_expr):
        raise BadRequestException(f"cron 表达式不合法: {cron_expr}")
    try:
        croniter(cron_expr)
    except Exception:
        raise BadRequestException(f"cron 表达式不合法: {cron_expr}")


def compute_next_run(cron_expr: str, base: datetime | None = None) -> datetime:
    """计算 cron 的下一次运行时间（以整分钟为基准，避免同一分钟重复触发）"""
    base = (base or datetime.now()).replace(second=0, microsecond=0)
    return croniter(cron_expr, base).get_next(datetime)


def _to_response(s: PlanSchedule) -> dict:
    return PlanScheduleResponse(
        id=s.id,
        plan_id=s.plan_id,
        created_by=s.created_by,
        name=s.name,
        cron_expr=s.cron_expr,
        mode=s.mode,
        case_ids=s.case_ids or None,
        enabled=s.enabled,
        description=s.description,
        is_running=s.is_running,
        last_run_at=s.last_run_at,
        last_status=s.last_status,
        last_skip_reason=s.last_skip_reason,
        next_run_at=s.next_run_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    ).model_dump()


# ---------- 执行上下文组装 ----------

async def _build_run_context(db: AsyncSession, schedule: PlanSchedule):
    """按任务范围组装批量执行上下文。

    返回 (entries, python_path, cwd)：
    - entries: list[(ptc_id, testcase_id, test_file, case_code)]
    - 项目缺自动化配置时返回 (None, None, None)；范围为空时返回 ([], python_path, cwd)
    """
    plan = await db.get(TestPlan, schedule.plan_id)
    if not plan:
        return None, None, None
    project = await db.get(Project, plan.project_id)
    if not project or not project.auto_root_path or not project.python_path:
        return None, None, None

    stmt = (
        select(PlanTestCase, TestCase)
        .join(TestCase, TestCase.id == PlanTestCase.testcase_id)
        .where(PlanTestCase.plan_id == schedule.plan_id)
    )
    if schedule.mode == "custom" and schedule.case_ids:
        stmt = stmt.where(TestCase.id.in_(schedule.case_ids))
    rows = list((await db.execute(stmt)).all())

    # 排序：custom 按创建时选择的顺序；full 按计划加入顺序
    if schedule.mode == "custom" and schedule.case_ids:
        order = {cid: i for i, cid in enumerate(schedule.case_ids)}
        rows.sort(key=lambda r: order.get(r.TestCase.id, 10**6))
    else:
        rows.sort(key=lambda r: r.PlanTestCase.id)

    entries = []
    for pt, tc in rows:
        if not tc.module_code or not tc.case_code:
            continue
        test_file = os.path.join(project.auto_root_path, f"{tc.module_code}.py")
        entries.append((pt.id, tc.id, test_file, tc.case_code))
    return entries, project.python_path, project.auto_root_path


# ---------- 触发与执行 ----------

async def _mark_skip(db: AsyncSession, schedule: PlanSchedule, reason: str) -> None:
    """任务被跳过：记录原因并推进到下一 cron 时刻（不触发执行）"""
    schedule.last_status = "skipped"
    schedule.last_skip_reason = reason
    schedule.next_run_at = compute_next_run(schedule.cron_expr)
    await db.commit()


async def trigger_schedule(schedule_id: int, *, manual: bool = False) -> None:
    """认领并启动一轮定时执行。

    - manual=True（立即执行）：任务忙碌/无用例等场景直接抛异常给出明确提示
    - manual=False（调度 tick）：冲突时静默记录 skipped 并推进下次时间
    """
    now = datetime.now()
    stale_before = now - timedelta(hours=settings.SCHEDULER_ZOMBIE_TIMEOUT_HOURS)

    async with AsyncSessionLocal() as db:
        s = await db.get(PlanSchedule, schedule_id)
        if not s:
            if manual:
                raise NotFoundException("定时任务不存在")
            return
        if not s.enabled and not manual:
            return

        # 僵尸复位：任务标记运行中但超过阈值，视为上次执行异常中断
        if s.is_running and s.running_since and s.running_since < stale_before:
            s.is_running = False
            s.running_since = None
            s.last_status = "error"
            s.last_skip_reason = "检测到上次执行异常中断，已自动复位"
            await db.commit()

        # 忙碌检测：任务自身运行中，或该计划存在执行中的用例（手动/上轮未结束）
        plan_busy = bool(
            (
                await db.execute(
                    select(func.count())
                    .select_from(PlanTestCase)
                    .where(
                        PlanTestCase.plan_id == s.plan_id,
                        PlanTestCase.result == "running",
                    )
                )
            ).scalar_one()
        )
        busy_reason = ""
        if s.is_running:
            busy_reason = "上一轮定时执行尚未结束"
        elif plan_busy:
            busy_reason = "该计划当前有执行在跑（手动或上一轮定时）"
        if busy_reason:
            if manual:
                raise BadRequestException(f"任务繁忙：{busy_reason}，请稍后再试")
            await _mark_skip(db, s, busy_reason)
            return

        # 组装执行上下文（fail-fast：先于认领检查配置/可用用例）
        entries, python_path, cwd = await _build_run_context(db, s)
        if entries is None:
            reason = "计划所属项目未配置自动化执行路径（auto_root_path/python_path）"
            if manual:
                raise BadRequestException(reason)
            await _mark_skip(db, s, reason)
            return
        if not entries:
            reason = "没有可自动执行的用例（需配置模块编码/用例编码）"
            if manual:
                raise BadRequestException(reason)
            await _mark_skip(db, s, reason)
            return

        # 认领 + 本轮用例预标记（同一事务提交）：
        # - 条件更新：仅当任务行 is_running=false 时认领成功（同一任务多 worker 仅一个成功）
        # - 预标记与认领同事务，保证其它任务的"忙碌检测"能及时感知本轮占用
        res = await db.execute(
            update(PlanSchedule)
            .where(
                PlanSchedule.id == schedule_id,
                PlanSchedule.is_running.is_(False),
            )
            .values(is_running=True, running_since=now)
        )
        if res.rowcount == 0:
            return
        plan_id = s.plan_id
        # 定时执行没有"当前登录用户"，测试人固定记为任务创建人
        creator_id = s.created_by
        ptc_rows = (
            (
                await db.execute(
                    select(PlanTestCase).where(
                        PlanTestCase.id.in_([e[0] for e in entries])
                    )
                )
            )
            .scalars()
            .all()
        )
        for pt in ptc_rows:
            if pt.plan_id == plan_id:
                pt.result = "running"
                pt.result_desc = "正在执行中..."
        await db.commit()

    # 认领成功：后台执行（与手动批量共用串行执行内核）
    task = asyncio.create_task(
        _run_schedule_batch(
            schedule_id, plan_id, creator_id, entries, python_path, cwd
        )
    )
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def _run_schedule_batch(
    schedule_id: int,
    plan_id: int,
    tester_id: int | None,
    entries: list[tuple[int, int, str, str]],
    python_path: str,
    cwd: str,
) -> None:
    """执行一轮定时批量（串行），结束后回写任务行状态"""
    started_at = datetime.now()
    try:
        # 用例的 running 预标记已在认领事务内完成，这里直接执行；
        # tester_id 为任务创建人，结果与执行日志的测试人均记为其本人
        await _execute_cases_sequential(
            AsyncSessionLocal, plan_id, entries, python_path, cwd, tester_id
        )
        # 若被"停止执行"中断，剩余用例会被标记为已终止
        if plan_id and await _count_aborted(plan_id, [e[0] for e in entries]):
            status, reason = "skipped", "执行过程中被用户停止"
        else:
            status, reason = "ok", None
    except Exception as e:
        status, reason = "error", f"执行异常: {str(e)[:180]}"
        logger.exception(f"定时执行失败 (schedule={schedule_id}): {e}")

    await _finalize_schedule(schedule_id, status, reason)

    # 整轮正常结束/被终止后，向计划绑定的企业微信机器人推送统计（旁路）
    if status in ("ok", "skipped"):
        from app.services.wecom_service import notify_plan_finished

        await notify_plan_finished(
            plan_id,
            "定时执行",
            tester_id,
            [e[0] for e in entries],
            started_at,
            datetime.now(),
        )


async def _finalize_schedule(schedule_id: int, status: str, reason: str | None) -> None:
    """回写任务行：清理运行标记、记录本次结果、推进下次运行时间"""
    try:
        async with AsyncSessionLocal() as db:
            s = await db.get(PlanSchedule, schedule_id)
            if not s:
                return
            s.is_running = False
            s.running_since = None
            s.last_run_at = datetime.now()
            s.last_status = status
            s.last_skip_reason = reason
            s.next_run_at = compute_next_run(s.cron_expr)
            await db.commit()
    except Exception as e:
        logger.warning(f"定时任务回写状态失败 (schedule={schedule_id}): {e}")


async def _count_aborted(plan_id: int, ptc_ids: list[int]) -> int:
    async with AsyncSessionLocal() as db:
        return (
            await db.execute(
                select(func.count())
                .select_from(PlanTestCase)
                .where(
                    PlanTestCase.id.in_(ptc_ids),
                    PlanTestCase.result == "skipped",
                    PlanTestCase.result_desc == "已被用户终止执行",
                )
            )
        ).scalar_one()


# ---------- 任务 CRUD ----------

class ScheduleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_plan(self, plan_id: int) -> TestPlan:
        plan = await self.db.get(TestPlan, plan_id)
        if not plan:
            raise NotFoundException("测试计划不存在")
        return plan

    async def get_schedule(self, plan_id: int, schedule_id: int) -> PlanSchedule:
        s = await self.db.get(PlanSchedule, schedule_id)
        if not s or s.plan_id != plan_id:
            raise NotFoundException("定时任务不存在")
        return s

    async def _check_plan_auto_config(self, plan: TestPlan) -> None:
        """定时任务依赖项目的自动化执行配置（与手动执行前置一致）"""
        project = await self.db.get(Project, plan.project_id)
        if not project:
            raise NotFoundException("所属项目不存在")
        if not project.auto_root_path:
            raise BadRequestException("所属项目未配置自动化根路径，无法创建定时执行")
        if not project.python_path:
            raise BadRequestException("所属项目未配置 Python 解释器路径，无法创建定时执行")

    async def _validate_payload(self, plan: TestPlan, cron_expr: str, mode: str, case_ids) -> None:
        _validate_cron(cron_expr)
        if mode not in ALLOWED_SCHEDULE_MODES:
            raise BadRequestException(f"执行范围不合法，应为: {', '.join(ALLOWED_SCHEDULE_MODES)}")
        if mode == "custom":
            ids = list(dict.fromkeys(case_ids or []))
            if not ids:
                raise BadRequestException("自定义范围模式必须至少选择一个用例")
            stmt = select(TestCase.id).where(
                TestCase.id.in_(ids),
                TestCase.project_id == plan.project_id,
            )
            found = set((await self.db.execute(stmt)).scalars().all())
            missing = [i for i in ids if i not in found]
            if missing:
                raise BadRequestException(f"部分用例不存在或不属于该计划所属项目: {missing}")
        # mode=full 时忽略 case_ids
        return None if mode == "full" else (list(dict.fromkeys(case_ids or [])))

    async def list_schedules(self, plan_id: int) -> list[dict]:
        await self._get_plan(plan_id)
        stmt = (
            select(PlanSchedule)
            .where(PlanSchedule.plan_id == plan_id)
            .order_by(PlanSchedule.id.desc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [_to_response(s) for s in rows]

    async def create_schedule(
        self, plan_id: int, data: PlanScheduleCreate, current_user_id: int
    ) -> dict:
        plan = await self._get_plan(plan_id)
        await self._check_plan_auto_config(plan)
        case_ids = await self._validate_payload(
            plan, data.cron_expr, data.mode, data.case_ids
        )
        s = PlanSchedule(
            plan_id=plan.id,
            created_by=current_user_id,
            name=data.name.strip(),
            cron_expr=data.cron_expr.strip(),
            mode=data.mode,
            case_ids=case_ids,
            enabled=True,
            description=data.description,
            next_run_at=compute_next_run(data.cron_expr),
        )
        self.db.add(s)
        await self.db.commit()
        await self.db.refresh(s)
        return _to_response(s)

    async def update_schedule(
        self, plan_id: int, schedule_id: int, data: PlanScheduleUpdate
    ) -> dict:
        s = await self.get_schedule(plan_id, schedule_id)
        plan = await self._get_plan(plan_id)
        payload = data.model_dump(exclude_unset=True)
        if not payload:
            raise BadRequestException("没有要更新的内容")

        cron_expr = payload.get("cron_expr", s.cron_expr).strip()
        mode = payload.get("mode", s.mode)
        # case_ids 若未传，维持原值；传了则按新模式校验
        raw_case_ids = payload.get("case_ids", s.case_ids) if mode == "custom" else None
        case_ids = await self._validate_payload(plan, cron_expr, mode, raw_case_ids)

        if "name" in payload:
            s.name = payload["name"].strip()
        if "cron_expr" in payload:
            s.cron_expr = cron_expr
        if "mode" in payload:
            s.mode = mode
        if mode == "full":
            s.case_ids = None
        else:
            s.case_ids = case_ids
        if "description" in payload:
            s.description = payload["description"]
        # cron 变化后重算下次运行时间；防止已过期任务在启用后立即补跑历史
        if "cron_expr" in payload:
            s.next_run_at = compute_next_run(cron_expr)
        await self.db.commit()
        await self.db.refresh(s)
        return _to_response(s)

    async def toggle_schedule(self, plan_id: int, schedule_id: int) -> dict:
        s = await self.get_schedule(plan_id, schedule_id)
        s.enabled = not s.enabled
        if s.enabled:
            # 启用时若上次时间已过期则重算，避免立即触发一次过期轮次
            if s.next_run_at is None or s.next_run_at <= datetime.now():
                s.next_run_at = compute_next_run(s.cron_expr)
        await self.db.commit()
        await self.db.refresh(s)
        return _to_response(s)

    async def delete_schedule(self, plan_id: int, schedule_id: int) -> None:
        s = await self.get_schedule(plan_id, schedule_id)
        await self.db.delete(s)
        await self.db.commit()
