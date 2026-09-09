from datetime import datetime

from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PlanSchedule(BaseModel):
    """定时执行任务：按 cron 周期触发计划内自动化用例执行

    - mode=full   每次触发该计划下所有具备 module_code/case_code 的用例
    - mode=custom 每次触发 case_ids 指定的子集
    - 到点防重复由调度器通过条件更新认领（is_running + next_run_at）
    """
    __tablename__ = "plan_schedules"

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 任务创建人：定时执行产生的结果/日志测试人记为创建人
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(50), nullable=False)
    # full / custom
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="full")
    # mode=custom 时的用例 id（plan 内 testcase_id）列表
    case_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 运行状态（DB 级，多进程/多 worker 下安全）
    is_running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    running_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 最近一次触发情况（记录在任务行上，不建独立运行历史表）
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ok/skipped/error
    last_skip_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 调度依据：下次应触发的时间（调度循环只查 next_run_at <= now 的任务）
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
