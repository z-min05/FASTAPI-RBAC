"""add agent tables

Revision ID: 0004_add_agent_tables
Revises: 0003_drop_testcase_run_order
Create Date: 2026-09-02

Agent（AI 助手）模块：会话（agent_conversations）+ 消息（agent_messages）+ Token 记录（agent_token_records）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_add_agent_tables'
down_revision: Union[str, None] = '0003_drop_testcase_run_order'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- Agent 会话 ----
    op.create_table(
        'agent_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('thread_id', sa.String(length=64), nullable=False),
        sa.Column('agent_key', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_conversations_thread_id', 'agent_conversations', ['thread_id'], unique=True)
    op.create_index('ix_agent_conversations_user_id', 'agent_conversations', ['user_id'])

    # ---- Agent 消息 ----
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

    # ---- Agent Token 记录 ----
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


def downgrade() -> None:
    op.drop_index('ix_agent_token_records_user_id', table_name='agent_token_records')
    op.drop_index('ix_agent_token_records_conversation_id', table_name='agent_token_records')
    op.drop_table('agent_token_records')
    op.drop_index('ix_agent_messages_conversation_id', table_name='agent_messages')
    op.drop_table('agent_messages')
    op.drop_index('ix_agent_conversations_user_id', table_name='agent_conversations')
    op.drop_index('ix_agent_conversations_thread_id', table_name='agent_conversations')
    op.drop_table('agent_conversations')
