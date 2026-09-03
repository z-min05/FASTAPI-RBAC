"""add auto_root_path, module_code, case_code for automation file generation

Revision ID: 0007_add_auto_fields
Revises: 0006_add_test_plans
Create Date: 2026-09-03

为 projects 表增加 auto_root_path（自动化测试根路径），
为 testcases 表增加 module_code（模块编码/文件名）、case_code（用例编码/函数名），
并增加部分唯一索引：UNIQUE(project_id, module_code, case_code) where both non-null。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007_add_auto_fields'
down_revision: Union[str, None] = '0006_add_test_plans'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # projects 加 auto_root_path
    op.add_column('projects', sa.Column('auto_root_path', sa.String(500), nullable=True))

    # testcases 加 module_code / case_code
    op.add_column('testcases', sa.Column('module_code', sa.String(100), nullable=True))
    op.add_column('testcases', sa.Column('case_code', sa.String(100), nullable=True))

    # 部分唯一索引：同一项目下 module_code+case_code 组合唯一（仅当两者均非空时）
    op.create_index(
        'ix_testcases_project_module_code',
        'testcases',
        ['project_id', 'module_code', 'case_code'],
        unique=True,
        postgresql_where=sa.text('module_code IS NOT NULL AND case_code IS NOT NULL'),
        mysql_using='btree',
    )


def downgrade() -> None:
    op.drop_index('ix_testcases_project_module_code', table_name='testcases')
    op.drop_column('testcases', 'case_code')
    op.drop_column('testcases', 'module_code')
    op.drop_column('projects', 'auto_root_path')