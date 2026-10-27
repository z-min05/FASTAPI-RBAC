"""扩展测试用例来源字段长度

导入的「来源」可能包含章节、设计决策和功能编号，50 个字符不足。

Revision ID: 0003_testcase_source_length
Revises: 0002_project_envs
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_testcase_source_length"
down_revision: Union[str, None] = "0002_project_envs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "testcases",
        "source",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    # 降级时必须缩短现有值，否则 PostgreSQL 无法把列缩回 VARCHAR(50)。
    op.execute(
        sa.text(
            "UPDATE testcases SET source = LEFT(source, 50) "
            "WHERE source IS NOT NULL AND char_length(source) > 50"
        )
    )
    op.alter_column(
        "testcases",
        "source",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
