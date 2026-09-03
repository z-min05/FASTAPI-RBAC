"""add test plans and plan testcases tables

Revision ID: 0006_add_test_plans
Revises: 0005_add_agent_llm_definition
Create Date: 2026-09-03

测试计划模块：计划（plans）+ 计划用例关联表（plan_testcases）。
- plans：一个计划归属一个项目；
- plan_testcases：仅关联 testcases（不复制用例内容），携带测试人/测试结果/结果描述执行字段。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_add_test_plans'
down_revision: Union[str, None] = '0005_add_agent_llm_definition'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 测试计划 ----
    op.create_table(
        'plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_plans_project_id', 'plans', ['project_id'])

    # ---- 计划用例关联表（含执行记录） ----
    op.create_table(
        'plan_testcases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('testcase_id', sa.Integer(), nullable=False),
        sa.Column('tester_id', sa.Integer(), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=True),
        sa.Column('result_desc', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['testcase_id'], ['testcases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tester_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'testcase_id', name='uq_plan_testcase'),
    )
    op.create_index('ix_plan_testcases_plan_id', 'plan_testcases', ['plan_id'])
    op.create_index('ix_plan_testcases_testcase_id', 'plan_testcases', ['testcase_id'])


def downgrade() -> None:
    op.drop_index('ix_plan_testcases_testcase_id', table_name='plan_testcases')
    op.drop_index('ix_plan_testcases_plan_id', table_name='plan_testcases')
    op.drop_table('plan_testcases')
    op.drop_index('ix_plans_project_id', table_name='plans')
    op.drop_table('plans')
