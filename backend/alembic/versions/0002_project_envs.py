"""自动化测试环境管理

- 环境快照：{项目根}/.envs/<name>.env
- 生效环境：{项目根}/.env（框架读取的那个文件）
- 「当前生效环境」由内容比对判定，不额外维护指针文件
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_project_envs"
down_revision: Union[str, None] = "0001_v1_0_0_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_envs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("remark", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uk_project_envs_project_name"),
    )
    op.create_index("ix_project_envs_project_id", "project_envs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_envs_project_id", table_name="project_envs")
    op.drop_table("project_envs")
