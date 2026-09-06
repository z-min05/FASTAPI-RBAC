"""v1.0.0 initial schema

合并并压扁开发阶段的 8 个增量迁移，创建当前最终完整表结构。

Revision ID: 0001_v1_0_0_initial
Revises: None
Create Date: 2026-09-04

注意：
- 已跳过 0003（drop testcases.run_order）：直接在创建时省略该列
- 跳过 0005 中 agent_conversations 的列迁移：直接创建最终形态
  （无 agent_key，包含 agent_id / config_hash / config_snapshot）
- 跳过 0007/0008 的 add_column：projects 直接包含 python_path / auto_root_path，
  testcases 直接包含 module_code / case_code
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_v1_0_0_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== 0001：RBAC 基础表 ====================
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('nickname', sa.String(length=50), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('avatar', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_superuser', sa.Boolean(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_roles_code', 'roles', ['code'], unique=True)

    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('module', sa.String(length=50), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_permissions_code', 'permissions', ['code'], unique=True)

    op.create_table(
        'menus',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('path', sa.String(length=200), nullable=True),
        sa.Column('component', sa.String(length=200), nullable=True),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('menu_type', sa.String(length=20), nullable=False, comment='directory/menu/button'),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('visible', sa.Boolean(), nullable=False),
        sa.Column('permission', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('sort', sa.Integer(), nullable=False),
        sa.Column('leader', sa.String(length=50), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('status', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.create_table(
        'operation_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=50), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('path', sa.String(length=255), nullable=False),
        sa.Column('params', sa.Text(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('ip', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True, comment='耗时(ms)'),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('response', sa.Text(), nullable=True, comment='响应内容'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 关联表：用户-角色 / 角色-权限 / 角色-菜单
    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'role_menus',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('menu_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['menu_id'], ['menus.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==================== 0002：项目 + 测试用例（无 run_order） ====================
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
        # 以下为 0007/0008 新增，压扁时直接包含
        sa.Column('auto_root_path', sa.String(500), nullable=True),
        sa.Column('python_path', sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_projects_code', 'projects', ['code'], unique=True)

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
        sa.Column('tags', sa.String(length=200), nullable=True),
        # 以下为 0007 新增，压扁时直接包含
        sa.Column('module_code', sa.String(100), nullable=True),
        sa.Column('case_code', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_testcases_project_id', 'testcases', ['project_id'])
    op.create_index('ix_testcases_module', 'testcases', ['module'])

    # ==================== 0007：部分唯一索引 ====================
    op.create_index(
        'ix_testcases_project_module_code',
        'testcases',
        ['project_id', 'module_code', 'case_code'],
        unique=True,
        postgresql_where=sa.text('module_code IS NOT NULL AND case_code IS NOT NULL'),
        mysql_using='btree',
    )

    # ==================== 0004：Agent 表 ====================
    op.create_table(
        'agent_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('thread_id', sa.String(length=64), nullable=False),
        # 直接最终形态（无 agent_key，含 agent_id）
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('config_hash', sa.String(length=64), nullable=True),
        sa.Column('config_snapshot', sa.JSON(), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_conversations_thread_id', 'agent_conversations', ['thread_id'], unique=True)
    op.create_index('ix_agent_conversations_user_id', 'agent_conversations', ['user_id'])

    op.create_table(
        'agent_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('token_total', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['agent_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_messages_conversation_id', 'agent_messages', ['conversation_id'])

    op.create_table(
        'agent_token_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('tool_calls', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['agent_conversations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_token_records_conversation_id', 'agent_token_records', ['conversation_id'])
    op.create_index('ix_agent_token_records_user_id', 'agent_token_records', ['user_id'])

    # ==================== 0005：Agent LLM + 定义 ====================
    op.create_table(
        'agent_llms',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.String(length=255), nullable=True),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=False),
        sa.Column('max_tokens', sa.Integer(), nullable=False),
        sa.Column('timeout', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('remark', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.create_table(
        'agent_definitions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('llm_id', sa.Integer(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('tools', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['llm_id'], ['agent_llms.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_definitions_user_id', 'agent_definitions', ['user_id'])
    op.create_index('ix_agent_definitions_llm_id', 'agent_definitions', ['llm_id'])

    # agent_conversations 外键到 agent_definitions
    op.create_foreign_key(
        'fk_agent_conversations_agent_id',
        'agent_conversations',
        'agent_definitions',
        ['agent_id'],
        ['id'],
    )

    # ==================== 0006：测试计划 ====================
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

    # ==================== v1.0.1：API 密钥 ====================
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, comment='密钥名称/描述'),
        sa.Column('key_hash', sa.String(length=255), nullable=False, comment='密钥哈希值'),
        sa.Column('key_prefix', sa.String(length=10), nullable=False, comment='密钥前缀'),
        sa.Column('role_id', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True, comment='过期时间'),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True, comment='最后使用时间'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    op.create_index('ix_api_keys_role_id', 'api_keys', ['role_id'])


def downgrade() -> None:
    # 反向顺序删除
    op.drop_index('ix_api_keys_role_id', table_name='api_keys')
    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    op.drop_table('api_keys')
    # 反向顺序删除
    op.drop_index('ix_plan_testcases_testcase_id', table_name='plan_testcases')
    op.drop_index('ix_plan_testcases_plan_id', table_name='plan_testcases')
    op.drop_table('plan_testcases')
    op.drop_index('ix_plans_project_id', table_name='plans')
    op.drop_table('plans')

    op.drop_constraint('fk_agent_conversations_agent_id', 'agent_conversations', type_='foreignkey')
    op.drop_index('ix_agent_definitions_llm_id', table_name='agent_definitions')
    op.drop_index('ix_agent_definitions_user_id', table_name='agent_definitions')
    op.drop_table('agent_definitions')
    op.drop_table('agent_llms')

    op.drop_index('ix_agent_token_records_user_id', table_name='agent_token_records')
    op.drop_index('ix_agent_token_records_conversation_id', table_name='agent_token_records')
    op.drop_table('agent_token_records')
    op.drop_index('ix_agent_messages_conversation_id', table_name='agent_messages')
    op.drop_table('agent_messages')
    op.drop_index('ix_agent_conversations_user_id', table_name='agent_conversations')
    op.drop_index('ix_agent_conversations_thread_id', table_name='agent_conversations')
    op.drop_table('agent_conversations')

    op.drop_index('ix_testcases_project_module_code', table_name='testcases')
    op.drop_index('ix_testcases_module', table_name='testcases')
    op.drop_index('ix_testcases_project_id', table_name='testcases')
    op.drop_table('testcases')
    op.drop_index('ix_projects_code', table_name='projects')
    op.drop_table('projects')

    op.drop_table('role_menus')
    op.drop_table('role_permissions')
    op.drop_table('user_roles')
    op.drop_table('operation_logs')
    op.drop_table('departments')
    op.drop_table('menus')
    op.drop_index('ix_permissions_code', table_name='permissions')
    op.drop_table('permissions')
    op.drop_index('ix_roles_code', table_name='roles')
    op.drop_table('roles')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')