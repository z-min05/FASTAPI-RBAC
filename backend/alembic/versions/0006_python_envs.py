"""python_envs 表：Python 虚拟环境（Miniconda）

Revision ID: 0006_python_envs
Revises: 0005_plan_agent_push
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_python_envs"
down_revision = "0005_plan_agent_push"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "python_envs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, comment="环境名（同时作为目录名，创建后不可改）"),
        sa.Column("python_version", sa.String(length=20), nullable=False, comment="Python 版本，如 3.11"),
        sa.Column("env_path", sa.String(length=500), nullable=False, comment="环境根路径"),
        sa.Column("python_path", sa.String(length=500), nullable=False, comment="解释器绝对路径"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending", comment="状态"),
        sa.Column("error_msg", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("last_output", sa.Text(), nullable=True, comment="最近一次 conda 命令输出摘要"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True, comment="最近一次与磁盘同步校验时间"),
        sa.Column("description", sa.Text(), nullable=True, comment="备注"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_python_envs_created_by", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_python_envs_name"),
        sa.UniqueConstraint("env_path", name="uq_python_envs_env_path"),
    )
    op.create_index("ix_python_envs_status", "python_envs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_python_envs_status", table_name="python_envs")
    op.drop_table("python_envs")
