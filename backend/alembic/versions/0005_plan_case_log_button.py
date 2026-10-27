"""补全测试计划「查看执行日志」按钮权限

测试计划用例操作栏的「日志」按钮使用 plan:case:list 权限，但 menus 表
缺少对应的 button 记录，导致角色授权界面无法勾选该按钮、其他角色看不到日志入口。

本迁移：
1. 在「测试计划」菜单下补一条 button 菜单（幂等）
2. 给已拥有 plan:case:list 权限的角色补授该按钮（幂等）

Revision ID: 0005_plan_case_log_button
Revises: 0004_api_key_owner_user
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_plan_case_log_button"
down_revision: Union[str, None] = "0004_api_key_owner_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 补按钮菜单：挂在「测试计划」菜单下
    op.execute(
        sa.text(
            """
            INSERT INTO menus (name, menu_type, permission, parent_id, sort, visible)
            SELECT '查看执行日志', 'button', 'plan:case:list', m.id, 12, TRUE
            FROM menus m
            WHERE m.path = '/test/plans'
              AND m.menu_type = 'menu'
              AND NOT EXISTS (
                  SELECT 1 FROM menus b
                  WHERE b.parent_id = m.id
                    AND b.menu_type = 'button'
                    AND b.permission = 'plan:case:list'
              )
            """
        )
    )

    # 2. 已拥有 plan:case:list 权限的角色，同步补授该按钮
    op.execute(
        sa.text(
            """
            INSERT INTO role_menus (role_id, menu_id)
            SELECT DISTINCT rp.role_id, b.id
            FROM role_permissions rp
            JOIN permissions p ON p.id = rp.permission_id
            JOIN menus b ON b.menu_type = 'button' AND b.permission = 'plan:case:list'
            WHERE p.code = 'plan:case:list'
              AND NOT EXISTS (
                  SELECT 1 FROM role_menus rm
                  WHERE rm.role_id = rp.role_id
                    AND rm.menu_id = b.id
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_menus
            WHERE menu_id IN (
                SELECT id FROM menus
                WHERE name = '查看执行日志'
                  AND menu_type = 'button'
                  AND permission = 'plan:case:list'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM menus
            WHERE name = '查看执行日志'
              AND menu_type = 'button'
              AND permission = 'plan:case:list'
            """
        )
    )
