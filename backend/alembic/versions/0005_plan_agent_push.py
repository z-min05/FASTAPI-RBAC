"""plans 绑定 AI 汇总 Agent + 会话（保存计划时创建）

Revision ID: 0005_plan_agent_push
Revises: 0004_wecom_robots_plan_robots
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_plan_agent_push"
down_revision = "0004_wecom_robots_plan_robots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("agent_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "plans",
        sa.Column("agent_conversation_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_plans_agent_id", "plans", "agent_definitions",
        ["agent_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_plans_agent_conversation_id", "plans", "agent_conversations",
        ["agent_conversation_id"], ["id"], ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_plans_agent_conversation_id", "plans", ["agent_conversation_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_plans_agent_conversation_id", "plans", type_="unique")
    op.drop_constraint("fk_plans_agent_conversation_id", "plans", type_="foreignkey")
    op.drop_constraint("fk_plans_agent_id", "plans", type_="foreignkey")
    op.drop_column("plans", "agent_conversation_id")
    op.drop_column("plans", "agent_id")