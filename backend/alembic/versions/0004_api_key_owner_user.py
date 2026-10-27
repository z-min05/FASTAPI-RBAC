"""API 密钥改为归属用户

密钥不再绑定角色，而是归属某个用户：
权限、操作人、责任人全部跟随该用户，避免虚拟用户/伪造 user_id。

Revision ID: 0004_api_key_owner_user
Revises: 0003_testcase_source_length
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_api_key_owner_user"
down_revision: Union[str, None] = "0003_testcase_source_length"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("user_id", sa.Integer(), nullable=True))

    # 历史密钥：以创建人作为归属用户回填
    op.execute(
        sa.text("UPDATE api_keys SET user_id = created_by WHERE user_id IS NULL")
    )

    op.create_foreign_key(
        "fk_api_keys_user_id_users",
        "api_keys",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])

    # 不再按角色授权：丢弃角色列（DROP COLUMN 会连带删除其外键）
    op.drop_index("ix_api_keys_role_id", table_name="api_keys")
    op.drop_column("api_keys", "role_id")


def downgrade() -> None:
    op.add_column("api_keys", sa.Column("role_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "api_keys_role_id_fkey",
        "api_keys",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_api_keys_role_id", "api_keys", ["role_id"])

    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_constraint("fk_api_keys_user_id_users", "api_keys", type_="foreignkey")
    op.drop_column("api_keys", "user_id")
