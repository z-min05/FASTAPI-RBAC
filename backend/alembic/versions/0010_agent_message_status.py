"""agent_messages 新增 status/error：失败轮同样落库并记录中断原因

Revision ID: 0010_agent_message_status
Revises: 0009_agent_workspace
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_agent_message_status"
down_revision = "0009_agent_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 存量消息全部来自成功路径（此前失败不落 assistant 消息），统一置为 ok
    op.add_column(
        "agent_messages",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="ok",
            comment="本轮结果：ok / failed",
        ),
    )
    op.add_column(
        "agent_messages",
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
            comment="失败原因（面向用户的提示，仅 status=failed 时有值）",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "error")
    op.drop_column("agent_messages", "status")
