"""plan_schedules 增加 created_by（任务创建人，作为定时执行结果的测试人）

Revision ID: 0003_plan_schedules_created_by
Revises: 0002_plan_schedules
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_plan_schedules_created_by"
down_revision = "0002_plan_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plan_schedules",
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "plan_schedules_created_by_fkey", "plan_schedules", type_="foreignkey"
    )
    op.drop_column("plan_schedules", "created_by")
