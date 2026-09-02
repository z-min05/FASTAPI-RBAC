"""add projects and testcases tables

Revision ID: 0002_add_projects_testcases
Revises: 0001_init_rbac
Create Date: 2026-09-02

测试管理模块：项目（projects）+ 用例（testcases），用例按项目划分。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_add_projects_testcases'
down_revision: Union[str, None] = '0001_init_rbac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 项目 ----
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_projects_code', 'projects', ['code'], unique=True)

    # ---- 测试用例 ----
    op.create_table(
        'testcases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('module', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('case_type', sa.String(length=30), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('precondition', sa.Text(), nullable=True),
        sa.Column('steps', sa.Text(), nullable=True),
        sa.Column('expected_result', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('run_order', sa.Integer(), nullable=True),
        sa.Column('tags', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_testcases_project_id', 'testcases', ['project_id'])
    op.create_index('ix_testcases_module', 'testcases', ['module'])


def downgrade() -> None:
    op.drop_index('ix_testcases_module', table_name='testcases')
    op.drop_index('ix_testcases_project_id', table_name='testcases')
    op.drop_table('testcases')
    op.drop_index('ix_projects_code', table_name='projects')
    op.drop_table('projects')
