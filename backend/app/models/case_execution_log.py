from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class CaseExecutionLog(BaseModel):
    """用例执行日志：一次用例指令（单个/批量内单条）执行产生的完整日志。

    每次执行落一行，保留历史；plan_testcases.result_desc 只存短摘要，
    完整日志存本表。最新一条不允许删除（前端控制 + 后端兜底校验）。
    """
    __tablename__ = "case_execution_logs"

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_testcase_id: Mapped[int] = mapped_column(
        ForeignKey("plan_testcases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 本次执行唯一标识（uuid），供追溯/增量读取
    run_token: Mapped[str] = mapped_column(String(64), nullable=False)
    # 结果：pass/fail/skipped/timeout/error
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 完整执行日志文本
    log_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tester_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
