"""add agent llm and definition tables

Revision ID: 0005_add_agent_llm_definition
Revises: 0004_add_agent_tables
Create Date: 2026-09-02

Agent V2：LLM 配置（agent_llms）+ 用户自建 Agent（agent_definitions）；
agent_conversations 移除 agent_key，新增 agent_id/config_hash/config_snapshot。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_add_agent_llm_definition'
down_revision: Union[str, None] = '0004_add_agent_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- LLM 配置（平台级，超管维护） ----
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

    # ---- Agent 定义（用户自建） ----
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

    # ---- 会话改造：agent_key -> agent_id + 配置快照 ----
    op.drop_column('agent_conversations', 'agent_key')
    op.add_column('agent_conversations', sa.Column('agent_id', sa.Integer(), nullable=True))
    op.add_column('agent_conversations', sa.Column('config_hash', sa.String(length=64), nullable=True))
    op.add_column('agent_conversations', sa.Column('config_snapshot', sa.JSON(), nullable=True))
    op.create_index('ix_agent_conversations_agent_id', 'agent_conversations', ['agent_id'])
    op.create_foreign_key(
        'fk_agent_conversations_agent_id',
        'agent_conversations',
        'agent_definitions',
        ['agent_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_agent_conversations_agent_id', 'agent_conversations', type_='foreignkey')
    op.drop_index('ix_agent_conversations_agent_id', table_name='agent_conversations')
    op.drop_column('agent_conversations', 'config_snapshot')
    op.drop_column('agent_conversations', 'config_hash')
    op.drop_column('agent_conversations', 'agent_id')
    op.add_column(
        'agent_conversations',
        sa.Column('agent_key', sa.String(length=50), nullable=False),
    )

    op.drop_index('ix_agent_definitions_llm_id', table_name='agent_definitions')
    op.drop_index('ix_agent_definitions_user_id', table_name='agent_definitions')
    op.drop_table('agent_definitions')
    op.drop_table('agent_llms')
