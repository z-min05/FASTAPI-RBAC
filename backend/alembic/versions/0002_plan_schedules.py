"""plan_schedules 定时执行任务表

Revision ID: 0002_plan_schedules
Revises: 0001_v1_0_0_initial
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_plan_schedules"
down_revision = "0001_v1_0_0_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("cron_expr", sa.String(length=50), nullable=False),
        sa.Column("mode", sa.String(length=10), server_default=sa.text("'full'"), nullable=False),
        sa.Column("case_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_running", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("running_since", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=10), nullable=True),
        sa.Column("last_skip_reason", sa.String(length=200), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_schedules_plan_id", "plan_schedules", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_schedules_plan_id", table_name="plan_schedules")
    op.drop_table("plan_schedules")
