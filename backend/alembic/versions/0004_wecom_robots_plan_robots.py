"""企业微信群机器人表 + plans.robot_ids（绑定推送机器人）

Revision ID: 0004_wecom_robots_plan_robots
Revises: 0003_plan_schedules_created_by
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_wecom_robots_plan_robots"
down_revision = "0003_plan_schedules_created_by"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wecom_robots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("webhook_url", sa.String(length=500), nullable=False),
        sa.Column("secret", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "plans",
        sa.Column("robot_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plans", "robot_ids")
    op.drop_table("wecom_robots")
