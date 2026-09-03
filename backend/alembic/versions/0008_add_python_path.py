"""add python_path to projects

Revision ID: 0008_add_python_path
Revises: 0007_add_auto_fields
Create Date: 2026-09-03

为 projects 表增加 python_path（Python 解释器路径），
允许自动化执行时调用指定 Python 环境执行 pytest。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008_add_python_path'
down_revision: Union[str, None] = '0007_add_auto_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # projects 加 python_path
    op.add_column('projects', sa.Column('python_path', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'python_path')
