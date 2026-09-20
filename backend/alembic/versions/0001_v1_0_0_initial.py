"""v1.0.0 初始表结构（单一压扁迁移）

本目录只保留这一个迁移文件：把开发阶段的全部增量迁移（原 0001 ~ 0010）压扁成
「一次建表」，`alembic upgrade head` 直接得到 v1.0.0 的最终完整结构。

压扁前迁移链（已全部合并进本文件，原文件已删除）：
  0001_v1_0_0_initial             RBAC 基础表 + 项目/用例 + Agent 会话/消息/Token + 测试计划
                                  （其内部又曾压扁过 v1.0.1 api_keys、v1.0.2 case_execution_logs）
  0002_plan_schedules             定时执行任务表 plan_schedules
  0003_plan_schedules_created_by  plan_schedules.created_by（任务创建人）
  0004_wecom_robots_plan_robots   企业微信群机器人表 + plans.robot_ids
  0005_plan_agent_push            plans.agent_id / plans.agent_conversation_id
  0006_python_envs                Python 虚拟环境表 python_envs
  0007_project_code_init          projects 代码初始化状态字段
  0008_testcase_modules           用例模块树 testcase_modules + testcases.module_id
  0009_agent_workspace            agent_definitions.workspace
  0010_agent_message_status       agent_messages.status / error

Revision ID: 0001_v1_0_0_initial
Revises: None
Create Date: 2026-09-04（压扁整合：2026-09-20）

压扁时有意省略的内容（历史数据修复）：
  原 0008 的「存量用例回填 module_id / module_code」与原 0009 的「存量 Agent 回填
  workspace 并清理已下线工具」都是针对"老库既有数据"的一次性 UPDATE。压扁后的
  迁移面向全新安装，建表时不存在存量数据，因此不再保留这些语句。

已经跑过老迁移链的数据库如何切换到本文件（结构等价，不要重跑 upgrade）：
    alembic stamp 0001_v1_0_0_initial
若库停留在旧的 0001（未包含 0002~0010 的表/列）状态，则 alembic 无法自动补结构，
需要按「备份数据 → 重建库 → upgrade → 导回数据」处理，或手工补齐缺失的表与列。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_v1_0_0_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== 1. RBAC 基础表 ====================

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("avatar", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "menus",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=True),
        sa.Column("component", sa.String(length=200), nullable=True),
        sa.Column("icon", sa.String(length=100), nullable=True),
        sa.Column("menu_type", sa.String(length=20), nullable=False, comment="目录/菜单/按钮"),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("permission", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("leader", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("params", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True, comment="耗时(ms)"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("response", sa.Text(), nullable=True, comment="响应内容"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 关联表：用户-角色 / 角色-权限 / 角色-菜单
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "role_menus",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("menu_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["menu_id"], ["menus.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ==================== 2. API 密钥 ====================

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, comment="密钥名称/描述"),
        sa.Column("key_hash", sa.String(length=255), nullable=False, comment="密钥哈希值"),
        sa.Column("key_prefix", sa.String(length=10), nullable=False, comment="密钥前缀（前8位），用于显示识别"),
        sa.Column("role_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True, comment="过期时间，NULL 表示永不过期"),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True, comment="最后使用时间"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_role_id", "api_keys", ["role_id"])

    # ==================== 3. 项目（含自动化代码初始化状态） ====================

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        # 自动化根路径（pytest 的 tests 目录）与项目解释器路径：由代码包初始化流程写入
        sa.Column("auto_root_path", sa.String(length=500), nullable=True),
        sa.Column("python_path", sa.String(length=500), nullable=True),
        # 自动化代码初始化状态机：none/pending/extracting/installing/ready/failed
        sa.Column(
            "code_init_status",
            sa.String(length=20),
            server_default="none",
            nullable=False,
            comment="代码初始化状态：none/pending/extracting/installing/ready/failed",
        ),
        sa.Column("code_init_error", sa.Text(), nullable=True, comment="代码初始化失败原因"),
        sa.Column("code_init_log", sa.Text(), nullable=True, comment="最近一次代码初始化输出"),
        sa.Column("code_init_at", sa.DateTime(), nullable=True, comment="最近一次代码初始化完成时间"),
        sa.Column("code_init_by", sa.Integer(), nullable=True, comment="代码初始化触发人"),
        sa.ForeignKeyConstraint(
            ["code_init_by"], ["users.id"], name="fk_projects_code_init_by", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_code", "projects", ["code"], unique=True)
    op.create_index("ix_projects_code_init_status", "projects", ["code_init_status"])

    # ==================== 4. 用例模块树 ====================

    op.create_table(
        "testcase_modules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False, comment="所属项目"),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="上级模块，NULL 为顶级"),
        sa.Column("name", sa.String(length=50), nullable=False, comment="模块名称（展示用）"),
        sa.Column(
            "code",
            sa.String(length=100),
            nullable=False,
            comment="磁盘名：目录名，或末级模块的 pytest 文件名（不含 .py）",
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("sort", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_testcase_modules_project_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["testcase_modules.id"], name="fk_testcase_modules_parent_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testcase_modules_project_id", "testcase_modules", ["project_id"])
    op.create_index("ix_testcase_modules_parent_id", "testcase_modules", ["parent_id"])
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

    # ==================== 5. 测试用例 ====================

    op.create_table(
        "testcases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("case_type", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("precondition", sa.Text(), nullable=True),
        sa.Column("steps", sa.Text(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("tags", sa.String(length=200), nullable=True),
        # 归属的末级模块（权威来源）与模块相对路径（不含 .py）
        sa.Column("module_id", sa.Integer(), nullable=True, comment="归属的末级模块"),
        sa.Column("module_code", sa.String(length=100), nullable=True),
        sa.Column("case_code", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["module_id"], ["testcase_modules.id"], name="fk_testcases_module_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testcases_project_id", "testcases", ["project_id"])
    op.create_index("ix_testcases_module", "testcases", ["module"])
    op.create_index("ix_testcases_module_id", "testcases", ["module_id"])
    # 同一项目下同一模块路径 + 用例编码唯一（两项均非空时才参与约束）
    op.create_index(
        "ix_testcases_project_module_code",
        "testcases",
        ["project_id", "module_code", "case_code"],
        unique=True,
        postgresql_where=sa.text("module_code IS NOT NULL AND case_code IS NOT NULL"),
        mysql_using="btree",
    )

    # ==================== 6. Agent（AI 助手） ====================

    # 6.1 LLM 配置（平台级，仅超管可增删改）
    op.create_table(
        "agent_llms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("timeout", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 6.2 Agent 定义（用户自建，含 bash 工具工作目录）
    op.create_table(
        "agent_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("llm_id", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column(
            "workspace",
            sa.String(length=500),
            nullable=True,
            comment="相对 bash 工作目录顶层目录的子路径，如 user_1/agent_2",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["llm_id"], ["agent_llms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_definitions_user_id", "agent_definitions", ["user_id"])
    op.create_index("ix_agent_definitions_llm_id", "agent_definitions", ["llm_id"])

    # 6.3 会话（最终形态：无 agent_key，含 agent_id / 配置快照 / hash）
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("config_hash", sa.String(length=64), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agent_definitions.id"], name="fk_agent_conversations_agent_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_conversations_thread_id", "agent_conversations", ["thread_id"], unique=True)
    op.create_index("ix_agent_conversations_user_id", "agent_conversations", ["user_id"])
    op.create_index("ix_agent_conversations_agent_id", "agent_conversations", ["agent_id"])

    # 6.4 会话消息（仅 user/assistant；失败轮同样落库，带 status/error）
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("token_total", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="ok",
            comment="本轮结果：ok / failed",
        ),
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
            comment="失败原因（面向用户的提示，仅 status=failed 时有值）",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])

    # 6.5 Token 消耗明细（审计保留，删除会话时不级联）
    op.create_table(
        "agent_token_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_token_records_conversation_id", "agent_token_records", ["conversation_id"])
    op.create_index("ix_agent_token_records_user_id", "agent_token_records", ["user_id"])

    # ==================== 7. 测试计划与执行 ====================

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        # 绑定的企业微信群机器人 id 数组（推送测试结果统计）
        sa.Column("robot_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # 绑定的 AI 结果汇总 Agent 与会话（保存计划时自动创建会话，一个计划唯一绑定一个会话）
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("agent_conversation_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agent_definitions.id"], name="fk_plans_agent_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["agent_conversation_id"],
            ["agent_conversations.id"],
            name="fk_plans_agent_conversation_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_conversation_id", name="uq_plans_agent_conversation_id"),
    )
    op.create_index("ix_plans_project_id", "plans", ["project_id"])

    op.create_table(
        "plan_testcases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("testcase_id", sa.Integer(), nullable=False),
        sa.Column("tester_id", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column("result_desc", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["testcase_id"], ["testcases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tester_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "testcase_id", name="uq_plan_testcase"),
    )
    op.create_index("ix_plan_testcases_plan_id", "plan_testcases", ["plan_id"])
    op.create_index("ix_plan_testcases_testcase_id", "plan_testcases", ["testcase_id"])

    op.create_table(
        "case_execution_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("plan_testcase_id", sa.Integer(), nullable=False),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column("log_content", sa.Text(), nullable=True),
        sa.Column("tester_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_testcase_id"], ["plan_testcases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tester_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_execution_logs_plan_id", "case_execution_logs", ["plan_id"])
    op.create_index(
        "ix_case_execution_logs_plan_testcase_id", "case_execution_logs", ["plan_testcase_id"]
    )

    # 定时执行任务：到点防重复由调度器通过条件更新认领（is_running + next_run_at）
    op.create_table(
        "plan_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        # 任务创建人：定时执行产生的结果/日志测试人记为创建人
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("cron_expr", sa.String(length=50), nullable=False),
        # full / custom
        sa.Column("mode", sa.String(length=10), server_default=sa.text("'full'"), nullable=False),
        sa.Column("case_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # 运行状态（DB 级，多进程/多 worker 下安全）
        sa.Column("is_running", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("running_since", sa.DateTime(), nullable=True),
        # 最近一次触发情况（记录在任务行上，不建独立运行历史表）
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=10), nullable=True),
        sa.Column("last_skip_reason", sa.String(length=200), nullable=True),
        # 调度依据：下次应触发的时间（调度循环只查 next_run_at <= now 的任务）
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_schedules_plan_id", "plan_schedules", ["plan_id"])

    # ==================== 8. 通知：企业微信群机器人 ====================

    op.create_table(
        "wecom_robots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, comment="机器人名称"),
        sa.Column("webhook_url", sa.String(length=500), nullable=False, comment="群机器人 webhook"),
        sa.Column("secret", sa.String(length=255), nullable=True, comment="加签密钥（加密存储）"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ==================== 9. Python 虚拟环境（Miniconda） ====================

    op.create_table(
        "python_envs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, comment="环境名（同时作为目录名，创建后不可改）"),
        sa.Column("python_version", sa.String(length=20), nullable=False, comment="Python 版本，如 3.11"),
        sa.Column("env_path", sa.String(length=500), nullable=False, comment="环境根路径"),
        sa.Column("python_path", sa.String(length=500), nullable=False, comment="解释器绝对路径"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
            comment="pending/creating/ready/failed/syncing/lost/deleting",
        ),
        sa.Column("error_msg", sa.Text(), nullable=True, comment="失败原因"),
        sa.Column("last_output", sa.Text(), nullable=True, comment="最近一次 conda 命令输出摘要"),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True, comment="最近一次与磁盘同步校验时间"),
        sa.Column("description", sa.Text(), nullable=True, comment="备注"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_python_envs_created_by", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_python_envs_name"),
        sa.UniqueConstraint("env_path", name="uq_python_envs_env_path"),
    )
    op.create_index("ix_python_envs_status", "python_envs", ["status"])


def downgrade() -> None:
    """按反向依赖顺序删除全部表（索引与表内约束随表一并删除）"""
    op.drop_table("python_envs")
    op.drop_table("wecom_robots")
    op.drop_table("plan_schedules")
    op.drop_table("case_execution_logs")
    op.drop_table("plan_testcases")
    op.drop_table("plans")
    op.drop_table("agent_token_records")
    op.drop_table("agent_messages")
    op.drop_table("agent_conversations")
    op.drop_table("agent_definitions")
    op.drop_table("agent_llms")
    op.drop_table("testcases")
    op.drop_table("testcase_modules")
    op.drop_table("projects")
    op.drop_table("api_keys")
    op.drop_table("role_menus")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("operation_logs")
    op.drop_table("departments")
    op.drop_table("menus")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
