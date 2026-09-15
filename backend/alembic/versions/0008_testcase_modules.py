"""testcase_modules 表：多级用例模块树；testcases 新增 module_id 并回填存量数据

Revision ID: 0008_testcase_modules
Revises: 0007_project_code_init
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_testcase_modules"
down_revision = "0007_project_code_init"
branch_labels = None
depends_on = None

# `module_code` 为空的存量用例统一挂到这棵末级模块下
_UNCategorized_CODE = "test_uncategorized"
_UNCategorized_NAME = "未分类"


def upgrade() -> None:
    op.create_table(
        "testcase_modules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False, comment="所属项目"),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="上级模块，NULL 为顶级"),
        sa.Column("name", sa.String(length=50), nullable=False, comment="模块名称（展示用）"),
        sa.Column(
            "code", sa.String(length=100), nullable=False,
            comment="磁盘名：目录名，或末级模块的 pytest 文件名（不含 .py）",
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("sort", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_testcase_modules_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["testcase_modules.id"], name="fk_testcase_modules_parent_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_testcase_modules_project_id", "testcase_modules", ["project_id"]
    )
    op.create_index(
        "ix_testcase_modules_parent_id", "testcase_modules", ["parent_id"]
    )
    # PostgreSQL 中 NULL 互不相等，顶级节点（parent_id 为 NULL）不会被普通唯一索引约束，
    # 必须用 COALESCE(parent_id, 0) 表达式索引把顶级统一映射为 0
    op.create_index(
        "ux_testcase_modules_sibling_name",
        "testcase_modules",
        [sa.text("project_id"), sa.text("COALESCE(parent_id, 0)"), sa.text("name")],
        unique=True,
    )
    op.create_index(
        "ux_testcase_modules_sibling_code",
        "testcase_modules",
        [sa.text("project_id"), sa.text("COALESCE(parent_id, 0)"), sa.text("code")],
        unique=True,
    )

    op.add_column(
        "testcases",
        sa.Column("module_id", sa.Integer(), nullable=True, comment="归属的末级模块"),
    )
    op.create_foreign_key(
        "fk_testcases_module_id", "testcases", "testcase_modules",
        ["module_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_testcases_module_id", "testcases", ["module_id"])

    _backfill_testcase_modules()


def downgrade() -> None:
    op.drop_index("ix_testcases_module_id", table_name="testcases")
    op.drop_constraint("fk_testcases_module_id", "testcases", type_="foreignkey")
    op.drop_column("testcases", "module_id")
    # 不恢复已被归一化的 module_code，也不恢复被回填的 test_uncategorized（已知限制）
    op.drop_table("testcase_modules")


# ---------- 存量数据回填（详见 docs/用例模块管理功能设计.md §9.2）----------

def _find_module_id(conn, project_id: int, parent_id: int | None, code: str) -> int | None:
    if parent_id is None:
        stmt = sa.text(
            "SELECT id FROM testcase_modules "
            "WHERE project_id = :pid AND parent_id IS NULL AND code = :code LIMIT 1"
        )
        params = {"pid": project_id, "code": code}
    else:
        stmt = sa.text(
            "SELECT id FROM testcase_modules "
            "WHERE project_id = :pid AND parent_id = :parent AND code = :code LIMIT 1"
        )
        params = {"pid": project_id, "parent": parent_id, "code": code}
    return conn.execute(stmt, params).scalar()


def _name_taken(conn, project_id: int, parent_id: int | None, name: str) -> bool:
    if parent_id is None:
        stmt = sa.text(
            "SELECT 1 FROM testcase_modules "
            "WHERE project_id = :pid AND parent_id IS NULL AND name = :name LIMIT 1"
        )
        params = {"pid": project_id, "name": name}
    else:
        stmt = sa.text(
            "SELECT 1 FROM testcase_modules "
            "WHERE project_id = :pid AND parent_id = :parent AND name = :name LIMIT 1"
        )
        params = {"pid": project_id, "parent": parent_id, "name": name}
    return conn.execute(stmt, params).scalar() is not None


def _get_or_create_module(
    conn, project_id: int, parent_id: int | None, code: str, preferred_name: str | None
) -> int:
    """按 (project_id, parent_id, code) 取模块，不存在则创建

    name 优先取存量 module 值；若该名称已被同级其它节点占用，则退回使用 code，
    避免脏数据导致唯一索引冲突、整个迁移失败。
    """
    existing = _find_module_id(conn, project_id, parent_id, code)
    if existing is not None:
        return existing

    name = (preferred_name or "").strip()[:50] or code
    if name != code and _name_taken(conn, project_id, parent_id, name):
        name = code

    return conn.execute(
        sa.text(
            "INSERT INTO testcase_modules "
            "(project_id, parent_id, name, code, sort, created_at, updated_at) "
            "VALUES (:pid, :parent, :name, :code, 0, now(), now()) RETURNING id"
        ),
        {"pid": project_id, "parent": parent_id, "name": name, "code": code},
    ).scalar()


def _backfill_testcase_modules() -> None:
    """按项目遍历存量用例，建出模块树并回填 module_id / module_code"""
    conn = op.get_bind()
    project_ids = [
        row[0]
        for row in conn.execute(
            sa.text("SELECT DISTINCT project_id FROM testcases WHERE project_id IS NOT NULL")
        ).fetchall()
    ]

    for project_id in project_ids:
        # A. 有 module_code 的用例：按 module_code 分组建节点
        groups = conn.execute(
            sa.text(
                "SELECT module_code, MIN(id) AS min_id FROM testcases "
                "WHERE project_id = :pid AND module_code IS NOT NULL AND module_code <> '' "
                "GROUP BY module_code"
            ),
            {"pid": project_id},
        ).fetchall()

        for module_code, min_id in groups:
            parts = [p for p in str(module_code).split("/") if p.strip()]
            if not parts:
                continue

            parent_id: int | None = None
            for part in parts[:-1]:
                parent_id = _get_or_create_module(conn, project_id, parent_id, part, part)

            leaf_name = conn.execute(
                sa.text("SELECT module FROM testcases WHERE id = :id"), {"id": min_id}
            ).scalar()
            leaf_id = _get_or_create_module(
                conn, project_id, parent_id, parts[-1], leaf_name
            )

            conn.execute(
                sa.text(
                    "UPDATE testcases SET module_id = :mid, module_code = :new_code "
                    "WHERE project_id = :pid AND module_code = :old_code"
                ),
                {
                    "mid": leaf_id,
                    "new_code": "/".join(parts),
                    "pid": project_id,
                    "old_code": module_code,
                },
            )

        # B. module_code 为空的用例：统一挂到「未分类」末级模块
        empty_filter = "project_id = :pid AND (module_code IS NULL OR module_code = '')"
        empty_count = conn.execute(
            sa.text(f"SELECT COUNT(*) FROM testcases WHERE {empty_filter}"),
            {"pid": project_id},
        ).scalar() or 0
        if not empty_count:
            continue

        uncategorized_id = _get_or_create_module(
            conn, project_id, None, _UNCategorized_CODE, _UNCategorized_NAME
        )
        conn.execute(
            sa.text(f"UPDATE testcases SET module_id = :mid WHERE {empty_filter}"),
            {"mid": uncategorized_id, "pid": project_id},
        )
        conn.execute(
            sa.text(
                f"UPDATE testcases SET module = COALESCE(NULLIF(module, ''), :name) "
                f"WHERE {empty_filter}"
            ),
            {"name": _UNCategorized_NAME, "pid": project_id},
        )
        # 回填 module_code 时按 case_code 去重：重复用例共用同一模块会让部分唯一索引
        # (project_id, module_code, case_code) 冲突，因此每个 (project_id, case_code)
        # 只回填 id 最小的那条，其余仅回填 module_id / module
        conn.execute(
            sa.text(
                "UPDATE testcases SET module_code = :code "
                "WHERE project_id = :pid AND module_id = :mid "
                "AND (case_code IS NULL OR id = ("
                "    SELECT MIN(t2.id) FROM testcases t2 "
                "    WHERE t2.project_id = :pid AND t2.module_id = :mid "
                "      AND t2.case_code = testcases.case_code))"
            ),
            {
                "code": _UNCategorized_CODE,
                "pid": project_id,
                "mid": uncategorized_id,
            },
        )
