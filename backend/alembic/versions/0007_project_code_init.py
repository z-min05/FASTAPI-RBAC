"""projects 表新增自动化代码初始化状态字段

Revision ID: 0007_project_code_init
Revises: 0006_python_envs
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_project_code_init"
down_revision = "0006_python_envs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "code_init_status", sa.String(length=20),
            server_default="none", nullable=False,
            comment="代码初始化状态：none/pending/extracting/installing/ready/failed",
        ),
    )
    op.add_column(
        "projects",
        sa.Column("code_init_error", sa.Text(), nullable=True, comment="代码初始化失败原因"),
    )
    op.add_column(
        "projects",
        sa.Column("code_init_log", sa.Text(), nullable=True, comment="最近一次代码初始化输出"),
    )
    op.add_column(
        "projects",
        sa.Column("code_init_at", sa.DateTime(), nullable=True, comment="最近一次代码初始化完成时间"),
    )
    op.add_column(
        "projects",
        sa.Column("code_init_by", sa.Integer(), nullable=True, comment="代码初始化触发人"),
    )
    op.create_foreign_key(
        "fk_projects_code_init_by", "projects", "users",
        ["code_init_by"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_projects_code_init_status", "projects", ["code_init_status"])


def downgrade() -> None:
    op.drop_index("ix_projects_code_init_status", table_name="projects")
    op.drop_constraint("fk_projects_code_init_by", "projects", type_="foreignkey")
    op.drop_column("projects", "code_init_by")
    op.drop_column("projects", "code_init_at")
    op.drop_column("projects", "code_init_log")
    op.drop_column("projects", "code_init_error")
    op.drop_column("projects", "code_init_status")
