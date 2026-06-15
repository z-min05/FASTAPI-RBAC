"""add cameras table

Revision ID: 001_add_cameras
Revises:
Create Date: 2026-06-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_cameras'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cameras',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, comment='摄像头名称'),
        sa.Column('ip', sa.String(length=50), nullable=False, comment='IP地址'),
        sa.Column('port', sa.Integer(), nullable=False, comment='ONVIF端口'),
        sa.Column('username', sa.String(length=50), nullable=False, comment='ONVIF用户名'),
        sa.Column('password', sa.String(length=100), nullable=False, comment='ONVIF密码'),
        sa.Column('rtsp_url', sa.String(length=500), nullable=True, comment='RTSP流地址'),
        sa.Column('snapshot_url', sa.String(length=500), nullable=True, comment='抓图URL'),
        sa.Column('location', sa.String(length=200), nullable=True, comment='安装位置'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('is_online', sa.Boolean(), nullable=False, comment='是否在线'),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='是否启用'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('cameras')
