"""agent_definitions 新增 workspace（相对 bash 工作目录根的 Agent 专属子目录），并清理存量 tools 中已下线的工具

Revision ID: 0009_agent_workspace
Revises: 0008_testcase_modules
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_agent_workspace"
down_revision = "0008_testcase_modules"
branch_labels = None
depends_on = None

# 本次改造下线的工具：calculator、search（替换为 bash）
_REMOVED_TOOLS = ["calculator", "search"]


def upgrade() -> None:
    # workspace 存的是「相对顶层工作目录的子路径」，绝对路径由服务端运行时解析
    # （顶层目录见 AGENT_WORKSPACE_ROOT，默认 backend/agent_workspaces）
    op.add_column(
        "agent_definitions",
        sa.Column(
            "workspace",
            sa.String(length=500),
            nullable=True,
            comment="相对 bash 工作目录顶层目录的子路径，如 user_1/agent_2",
        ),
    )

    # 存量 Agent 回填为按 id 推导的默认子目录，与新建时的命名规则保持一致
    op.execute(
        """
        UPDATE agent_definitions
        SET workspace = 'user_' || user_id || '/agent_' || id
        WHERE workspace IS NULL OR workspace = ''
        """
    )

    # 清理存量勾选：tools 为 JSON（非 JSONB），先转 jsonb 才能用 `-` 删数组元素。
    # 保留下来的 tool 名称全部保留，仅移除已下线的两个。
    names = ", ".join(f"'{n}'" for n in _REMOVED_TOOLS)
    op.execute(
        f"""
        UPDATE agent_definitions
        SET tools = ((tools::jsonb - '{_REMOVED_TOOLS[0]}') - '{_REMOVED_TOOLS[1]}')::json
        WHERE tools IS NOT NULL
          AND tools::jsonb ?| array[{names}]
        """
    )


def downgrade() -> None:
    op.drop_column("agent_definitions", "workspace")
    # 被移除的工具已不存在，降级不恢复 tools 内容（需人工处理）
