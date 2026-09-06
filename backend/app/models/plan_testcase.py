from sqlalchemy import String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class PlanTestCase(BaseModel):
    """计划用例：计划与用例的关联记录，用例内容不复制，仅关联 testcase_id；
    执行字段（测试人/结果/结果描述）记录在关联行上，便于追溯与统计。"""
    __tablename__ = "plan_testcases"
    __table_args__ = (
        UniqueConstraint("plan_id", "testcase_id", name="uq_plan_testcase"),
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    testcase_id: Mapped[int] = mapped_column(
        ForeignKey("testcases.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tester_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 测试结果：pass/fail/blocked/skipped，未执行为 NULL
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    result_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
