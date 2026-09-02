"""drop testcase run_order column

Revision ID: 0003_drop_testcase_run_order
Revises: 0002_add_projects_testcases
Create Date: 2026-09-02

移除用例表 run_order（执行顺序）字段：用例管理阶段无需执行顺序。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_drop_testcase_run_order'
down_revision: Union[str, None] = '0002_add_projects_testcases'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('testcases', 'run_order')


def downgrade() -> None:
    op.add_column('testcases', sa.Column('run_order', sa.Integer(), nullable=True))
