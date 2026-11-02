"""工具管理模块

- 新增 tools 表：工具名称/描述 + 压缩包与 README 的存储信息
- 新增 API 权限、菜单、按钮，并为 admin / user 角色补授权（user 默认只读）
- 文件实体存放在 TOOL_STORAGE_DIR，表中只存相对文件名

Revision ID: 0006_tools
Revises: 0005_plan_case_log_button
Create Date: 2026-11-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_tools"
down_revision: Union[str, None] = "0005_plan_case_log_button"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSIONS = [
    ("工具列表", "tool:list", "tool", "list"),
    ("上传工具", "tool:create", "tool", "create"),
    ("下载工具压缩包", "tool:download", "tool", "download"),
    ("删除工具", "tool:delete", "tool", "delete"),
]

BUTTONS = [
    ("上传工具", "tool:create", 1),
    ("下载工具包", "tool:download", 2),
    ("删除工具", "tool:delete", 3),
]


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("package_filename", sa.String(length=255), nullable=False),
        sa.Column("package_path", sa.String(length=500), nullable=False),
        sa.Column("package_size", sa.BigInteger(), nullable=False),
        sa.Column("readme_filename", sa.String(length=255), nullable=False),
        sa.Column("readme_path", sa.String(length=500), nullable=False),
        sa.Column("readme_size", sa.BigInteger(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    conn = op.get_bind()

    # 1. API 权限
    # 注意：代码列同时出现在 SELECT 与 NOT EXISTS 中时，asyncpg 无法推断同一个
    # 参数的类型（text / varchar 冲突），因此拆成两个参数并显式 CAST。
    for name, code, module, action in PERMISSIONS:
        conn.execute(
            sa.text(
                """
                INSERT INTO permissions (name, code, module, action)
                SELECT CAST(:name AS VARCHAR(50)), CAST(:code AS VARCHAR(100)),
                       CAST(:module AS VARCHAR(50)), CAST(:action AS VARCHAR(50))
                WHERE NOT EXISTS (
                    SELECT 1 FROM permissions WHERE code = CAST(:code_check AS VARCHAR(100))
                )
                """
            ),
            {
                "name": name,
                "code": code,
                "module": module,
                "action": action,
                "code_check": code,
            },
        )

    # 2. 一级菜单「工具管理」
    conn.execute(
        sa.text(
            """
            INSERT INTO menus (name, path, component, icon, menu_type, sort, visible, permission)
            SELECT '工具管理', '/tools', 'tools/ToolManage', 'ToolOutlined', 'menu',
                   COALESCE((SELECT MAX(sort) FROM menus WHERE parent_id IS NULL), 0) + 1,
                   TRUE, 'tool:list'
            WHERE NOT EXISTS (
                SELECT 1 FROM menus WHERE path = '/tools' AND menu_type = 'menu'
            )
            """
        )
    )

    # 3. 按钮权限
    for name, perm, sort in BUTTONS:
        conn.execute(
            sa.text(
                """
                INSERT INTO menus (name, menu_type, permission, parent_id, sort, visible)
                SELECT CAST(:name AS VARCHAR(50)), 'button',
                       CAST(:perm AS VARCHAR(100)), m.id,
                       CAST(:sort AS INTEGER), TRUE
                FROM menus m
                WHERE m.path = '/tools' AND m.menu_type = 'menu'
                  AND NOT EXISTS (
                      SELECT 1 FROM menus b
                      WHERE b.parent_id = m.id
                        AND b.menu_type = 'button'
                        AND b.permission = CAST(:perm_check AS VARCHAR(100))
                  )
                """
            ),
            {"name": name, "perm": perm, "sort": sort, "perm_check": perm},
        )

    # 4. 角色授权：admin 全部；user 仅列表（只读）
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r CROSS JOIN permissions p
            WHERE r.code = 'admin' AND p.code LIKE 'tool:%'
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions rp
                  WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r CROSS JOIN permissions p
            WHERE r.code = 'user' AND p.code = 'tool:list'
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions rp
                  WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO role_menus (role_id, menu_id)
            SELECT r.id, m.id
            FROM roles r CROSS JOIN menus m
            WHERE r.code = 'admin'
              AND (
                  m.path = '/tools'
                  OR m.parent_id IN (SELECT id FROM menus WHERE path = '/tools' AND menu_type = 'menu')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM role_menus rm
                  WHERE rm.role_id = r.id AND rm.menu_id = m.id
              )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO role_menus (role_id, menu_id)
            SELECT r.id, m.id
            FROM roles r CROSS JOIN menus m
            WHERE r.code = 'user' AND m.path = '/tools' AND m.menu_type = 'menu'
              AND NOT EXISTS (
                  SELECT 1 FROM role_menus rm
                  WHERE rm.role_id = r.id AND rm.menu_id = m.id
              )
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM role_menus
            WHERE menu_id IN (
                SELECT id FROM menus
                WHERE path = '/tools'
                   OR parent_id IN (SELECT id FROM menus WHERE path = '/tools' AND menu_type = 'menu')
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM menus
            WHERE path = '/tools'
               OR parent_id IN (SELECT id FROM menus WHERE path = '/tools' AND menu_type = 'menu')
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (SELECT id FROM permissions WHERE code LIKE 'tool:%')
            """
        )
    )
    conn.execute(sa.text("DELETE FROM permissions WHERE code LIKE 'tool:%'"))
    op.drop_table("tools")
