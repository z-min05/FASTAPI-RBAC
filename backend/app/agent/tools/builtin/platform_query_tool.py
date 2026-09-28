"""内置工具：测试平台数据查询（项目 / 用例模块 / 用例 / 测试计划）—— 只读。

设计要点：
- **单一工具 + `target` 参数**：四类查询共用一套筛选/分页参数，LLM 只需记一个工具名，
  避免同时暴露 4 个近似工具造成选择困难；
- **只读**：仅查询，不写库、不触发执行；参数不合法时返回可读提示，不向推理流程抛异常；
- **与页面同源**：复用平台既有服务/仓储层的查询语义（分页、模糊搜索、模块子树展开、
  计划结果统计），保证 Agent 看到的数据与 Web 页面一致；
- **自带数据库会话**：LangGraph 的同步 `invoke` 在 worker 线程内调用工具，而服务主连接池
  的连接绑定在主事件循环上，跨事件循环复用会报 "attached to a different loop"，
  故工具用自己的引擎（NullPool 现开现关），不复用 `app.db.session.engine`。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import json
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.pagination import PaginationParams
from app.models.plan import TestPlan
from app.models.project import Project
from app.models.testcase import TestCase
from app.utils.logger import logger

# 注册表中的工具名
QUERY_TOOL_NAME = "query_platform"

# 分页默认值与上限（上限同时约束单次返回给模型的文本长度）
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# target 归一化：英文单/复数与中文别名都接受
_TARGET_ALIASES: dict[str, str] = {
    "project": "projects",
    "projects": "projects",
    "项目": "projects",
    "module": "modules",
    "modules": "modules",
    "模块": "modules",
    "用例模块": "modules",
    "testcase": "testcases",
    "testcases": "testcases",
    "case": "testcases",
    "用例": "testcases",
    "plan": "plans",
    "plans": "plans",
    "计划": "plans",
    "测试计划": "plans",
}

# 各 target 生效的筛选参数（回显用，避免把无关参数写进返回结果）
_TARGET_FILTER_KEYS: dict[str, tuple[str, ...]] = {
    "projects": ("keyword", "project", "status"),
    "modules": ("keyword", "project", "module_id"),
    "testcases": ("keyword", "project", "module_id", "priority", "status", "detail"),
    "plans": ("keyword", "project", "status"),
}

# projects 的 status 取值（页面上的「启用 / 停用」）
_ACTIVE_TRUE = {"active", "enabled", "enable", "true", "1", "yes", "启用", "已启用"}
_ACTIVE_FALSE = {"inactive", "disabled", "disable", "false", "0", "no", "停用", "已停用"}


class _QueryError(Exception):
    """参数 / 数据问题：转成给 LLM 看的提示性错误，不打断推理。"""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


# ==================== 数据库会话 ====================

# 测试注入点：provider() 返回一个异步上下文管理器，产出 AsyncSession
_session_provider: Callable[[], Any] | None = None
_engine: AsyncEngine | None = None
_engine_lock = threading.Lock()


def _get_engine() -> AsyncEngine:
    """工具专用引擎（惰性单例）。

    NullPool：连接不缓存，每次现开现关，因而可安全用于「每个工具调用一个新事件循环」
    的 worker 线程，不与主服务的事件循环 / 连接池发生跨循环复用。
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = create_async_engine(
                    settings.DATABASE_URL,
                    poolclass=NullPool,
                    pool_pre_ping=True,
                )
    return _engine


@contextlib.asynccontextmanager
async def _default_session_scope() -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(
        _get_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


def set_session_scope(provider: Callable[[], Any] | None) -> None:
    """替换工具的数据来源（测试注入用）；传 None 恢复默认。"""
    global _session_provider
    _session_provider = provider


def _session_scope():
    return (_session_provider or _default_session_scope)()


def _run_db(handler: Callable[[AsyncSession], Awaitable[dict]]) -> dict:
    """在独立事件循环中执行一段数据库查询，返回可直接序列化的 dict。"""

    async def _main() -> dict:
        async with _session_scope() as session:
            return await handler(session)

    coro = _main()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 常规路径：工具在 LangGraph 的 worker 线程内被同步调用，本线程没有事件循环
        return asyncio.run(coro)
    # 兜底：调用方线程已有事件循环（如测试直接调用）时换线程跑，避免嵌套循环
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ==================== 小工具 ====================


def _dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _fmt_dt(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def _total_pages(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size if total > 0 else 0


def _echo_filters(args: dict) -> dict:
    keys = _TARGET_FILTER_KEYS.get(args["target"], ())
    return {k: args[k] for k in keys if args.get(k)}


def _payload(
    args: dict,
    total: int,
    page: int,
    page_size: int,
    total_pages: int,
    items: list[dict],
) -> dict:
    payload = {
        "target": args["target"],
        "filters": _echo_filters(args),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "returned": len(items),
        "items": items,
    }
    if total == 0:
        payload["hint"] = "没有匹配的数据，可放宽筛选条件（去掉 keyword / status / priority 或换项目）后重试"
    elif page * page_size < total:
        payload["hint"] = (
            f"命中 {total} 条，本次只返回 {len(items)} 条：可传 page={page + 1} 翻页，"
            "或用 keyword / module_id / status 缩小范围"
        )
    return payload


def _project_brief(project: Project | None) -> dict | None:
    if project is None:
        return None
    return {"id": project.id, "code": project.code, "name": project.name}


async def _resolve_project(session: AsyncSession, raw: str) -> Project | None:
    """把「项目 ID 或项目编码」解析成项目；为空返回 None（表示不限项目）。"""
    value = (raw or "").strip()
    if not value:
        return None

    stmt = select(Project)
    project = None
    if value.isdigit():
        project = (
            await session.execute(stmt.where(Project.id == int(value)))
        ).scalars().first()
    if project is None:
        project = (
            await session.execute(stmt.where(Project.code == value))
        ).scalars().first()
    if project is None:
        raise _QueryError(
            f"项目不存在：{value}",
            hint='可先查 target="projects" 获取项目 ID / 编码，再带上 project 参数',
        )
    return project


# ==================== 查询实现 ====================


async def _query_projects(session: AsyncSession, args: dict, page: int, size: int) -> dict:
    from app.repositories.project_repo import ProjectRepository

    is_active = _parse_active_flag(args["status"])
    target_project = (
        await _resolve_project(session, args["project"]) if args["project"] else None
    )
    if target_project is not None:
        # 指定了项目：精确返回该项目（keyword / status 退化为附加校验条件）
        keyword = args["keyword"].lower()
        matched = (
            not keyword
            or keyword in (target_project.name or "").lower()
            or keyword in (target_project.code or "").lower()
        ) and (is_active is None or bool(target_project.is_active) == is_active)
        projects = [target_project] if matched else []
        total = len(projects)
    else:
        result = await ProjectRepository(session).get_paginated(
            PaginationParams(page=page, page_size=size),
            keyword=args["keyword"] or None,
            is_active=is_active,
        )
        projects = result.items
        total = result.total

    tc_counts, plan_counts = await _count_by_project(session, [p.id for p in projects])
    items = [_project_item(p, tc_counts, plan_counts) for p in projects]
    payload = _payload(args, total, page, size, _total_pages(total, size), items)
    payload["resolved_project"] = _project_brief(target_project)
    return payload


def _project_item(project: Project, tc_counts: dict[int, int], plan_counts: dict[int, int]) -> dict:
    return {
        "id": project.id,
        "code": project.code,
        "name": project.name,
        "is_active": project.is_active,
        "description": project.description,
        "code_init_status": project.code_init_status,
        "testcase_count": tc_counts.get(project.id, 0),
        "plan_count": plan_counts.get(project.id, 0),
        "created_at": _fmt_dt(project.created_at),
    }


def _parse_active_flag(status: str) -> bool | None:
    value = (status or "").strip().lower()
    if not value:
        return None
    if value in _ACTIVE_TRUE:
        return True
    if value in _ACTIVE_FALSE:
        return False
    raise _QueryError(
        f"项目的状态取值不合法：{status}",
        hint='projects 的 status 只支持 active（启用）/ inactive（停用），留空表示全部',
    )


async def _count_by_project(
    session: AsyncSession, project_ids: list[int]
) -> tuple[dict[int, int], dict[int, int]]:
    """批量统计各项目下的用例数与计划数"""
    ids = sorted({pid for pid in project_ids if pid})
    if not ids:
        return {}, {}
    tc_rows = await session.execute(
        select(TestCase.project_id, func.count(TestCase.id))
        .where(TestCase.project_id.in_(ids))
        .group_by(TestCase.project_id)
    )
    plan_rows = await session.execute(
        select(TestPlan.project_id, func.count(TestPlan.id))
        .where(TestPlan.project_id.in_(ids))
        .group_by(TestPlan.project_id)
    )
    return (
        {pid: count for pid, count in tc_rows.all()},
        {pid: count for pid, count in plan_rows.all()},
    )


async def _query_modules(session: AsyncSession, args: dict, page: int, size: int) -> dict:
    from app.services.testcase_module_service import TestCaseModuleService

    project = await _resolve_project(session, args["project"])
    if project is None:
        raise _QueryError(
            "查询用例模块必须指定项目",
            hint='请带上 project=项目 ID 或项目编码（可先查 target="projects" 拿项目列表）',
        )

    tree = await TestCaseModuleService(session).get_tree(project.id)
    if args["module_id"]:
        node = _find_module(tree, args["module_id"])
        if node is None:
            raise _QueryError(
                f"模块不存在或不属于项目 {project.code}：module_id={args['module_id']}",
                hint='可先查 target="modules"（不带 module_id）获取该项目的模块树与模块 ID',
            )
        tree = [node]

    items = _flatten_modules(tree)
    if args["keyword"]:
        needle = args["keyword"].lower()
        items = [
            it
            for it in items
            if needle in str(it["name"]).lower()
            or needle in str(it["code"]).lower()
            or needle in str(it["module_path"]).lower()
        ]

    total = len(items)
    start = (page - 1) * size
    payload = _payload(
        args, total, page, size, _total_pages(total, size), items[start : start + size]
    )
    payload["resolved_project"] = _project_brief(project)
    return payload


def _find_module(nodes: list[dict], module_id: int) -> dict | None:
    for node in nodes:
        if node.get("id") == module_id:
            return node
        found = _find_module(node.get("children") or [], module_id)
        if found is not None:
            return found
    return None


def _flatten_modules(nodes: list[dict], level: int = 0) -> list[dict]:
    """模块树按「父节点在前」的深度优先顺序拉平，level 表示层级（0 为顶级）"""
    items: list[dict] = []
    for node in nodes:
        items.append(
            {
                "id": node.get("id"),
                "parent_id": node.get("parent_id"),
                "name": node.get("name"),
                "code": node.get("code"),
                "module_path": node.get("module_path"),
                "level": level,
                "is_leaf": node.get("is_leaf"),
                "case_count": node.get("case_count", 0),
                "total_case_count": node.get("total_case_count", 0),
                "description": node.get("description"),
            }
        )
        children = node.get("children") or []
        if children:
            items.extend(_flatten_modules(children, level + 1))
    return items


async def _query_testcases(session: AsyncSession, args: dict, page: int, size: int) -> dict:
    from app.schemas.testcase import ALLOWED_PRIORITIES, ALLOWED_STATUS
    from app.services.testcase_service import TestCaseService

    priority = args["priority"]
    if priority and priority not in ALLOWED_PRIORITIES:
        raise _QueryError(
            f"优先级取值不合法：{priority}",
            hint=f"可用值：{', '.join(ALLOWED_PRIORITIES)}",
        )
    status = args["status"]
    if status and status not in ALLOWED_STATUS:
        raise _QueryError(
            f"用例状态取值不合法：{status}",
            hint=f"可用值：{', '.join(ALLOWED_STATUS)}",
        )

    project = await _resolve_project(session, args["project"])
    result = await TestCaseService(session).get_testcases(
        PaginationParams(page=page, page_size=size),
        project_id=project.id if project else None,
        priority=priority or None,
        status=status or None,
        keyword=args["keyword"] or None,
        module_id=args["module_id"] or None,
        include_children=True,
    )
    items = [_testcase_item(tc, args["detail"]) for tc in result.items]
    payload = _payload(args, result.total, page, size, result.total_pages, items)
    payload["resolved_project"] = _project_brief(project)
    return payload


def _testcase_item(tc: dict, detail: bool) -> dict:
    item = {
        "id": tc.get("id"),
        "title": tc.get("title"),
        "project_id": tc.get("project_id"),
        "project_code": tc.get("project_code"),
        "project_name": tc.get("project_name"),
        "module_id": tc.get("module_id"),
        "module": tc.get("module"),
        "module_code": tc.get("module_code"),
        "priority": tc.get("priority"),
        "case_type": tc.get("case_type"),
        "status": tc.get("status"),
        "tags": tc.get("tags"),
        "case_code": tc.get("case_code"),
        "created_at": _fmt_dt(tc.get("created_at")),
    }
    if detail:
        item.update(
            {
                "source": tc.get("source"),
                "precondition": tc.get("precondition"),
                "steps": tc.get("steps"),
                "expected_result": tc.get("expected_result"),
            }
        )
    return item


async def _query_plans(session: AsyncSession, args: dict, page: int, size: int) -> dict:
    from app.schemas.plan import ALLOWED_PLAN_STATUS
    from app.services.plan_service import PlanService

    status = args["status"]
    if status and status not in ALLOWED_PLAN_STATUS:
        raise _QueryError(
            f"测试计划状态取值不合法：{status}",
            hint=f"可用值：{', '.join(ALLOWED_PLAN_STATUS)}",
        )

    project = await _resolve_project(session, args["project"])
    result = await PlanService(session).get_plans(
        PaginationParams(page=page, page_size=size),
        project_id=project.id if project else None,
        status=status or None,
        keyword=args["keyword"] or None,
    )
    items = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "project_id": p.get("project_id"),
            "project_code": p.get("project_code"),
            "project_name": p.get("project_name"),
            "status": p.get("status"),
            "description": p.get("description"),
            "case_count": p.get("case_count", 0),
            "result_stats": p.get("result_stats") or {},
            "robots": [r.get("name") for r in (p.get("robots") or [])],
            "created_at": _fmt_dt(p.get("created_at")),
            "updated_at": _fmt_dt(p.get("updated_at")),
        }
        for p in result.items
    ]
    payload = _payload(args, result.total, page, size, result.total_pages, items)
    payload["resolved_project"] = _project_brief(project)
    return payload


async def _dispatch(session: AsyncSession, args: dict, page: int, size: int) -> dict:
    target = args["target"]
    if target == "projects":
        return await _query_projects(session, args, page, size)
    if target == "modules":
        return await _query_modules(session, args, page, size)
    if target == "testcases":
        return await _query_testcases(session, args, page, size)
    return await _query_plans(session, args, page, size)


# ==================== 工具入口 ====================


def _execute(
    target: str,
    keyword: str,
    project: str,
    module_id: int,
    status: str,
    priority: str,
    page: int,
    page_size: int,
    detail: bool,
) -> str:
    raw_target = (target or "").strip()
    resolved = _TARGET_ALIASES.get(raw_target) or _TARGET_ALIASES.get(raw_target.lower())
    if resolved is None:
        return _dumps(
            {
                "target": raw_target,
                "error": f"未知的查询对象：{raw_target or '(空)'}",
                "hint": "target 只能取 projects（项目）/ modules（用例模块）/ testcases（用例）/ plans（测试计划）",
            }
        )

    try:
        args = {
            "target": resolved,
            "keyword": (keyword or "").strip(),
            "project": (project or "").strip(),
            "module_id": int(module_id or 0),
            "status": (status or "").strip(),
            "priority": (priority or "").strip().upper(),
            "detail": bool(detail),
        }
        page_no = max(1, int(page))
        size_no = min(MAX_PAGE_SIZE, max(1, int(page_size)))
    except (TypeError, ValueError):
        return _dumps(
            {
                "target": resolved,
                "error": "参数类型不正确：module_id / page / page_size 必须是整数",
                "hint": f"page 从 1 开始，page_size 取值范围 1~{MAX_PAGE_SIZE}",
            }
        )

    try:
        payload = _run_db(lambda session: _dispatch(session, args, page_no, size_no))
    except _QueryError as exc:
        body: dict[str, Any] = {"target": resolved, "error": str(exc)}
        if exc.hint:
            body["hint"] = exc.hint
        return _dumps(body)
    except Exception as exc:  # noqa: BLE001 - 工具不向推理流程抛异常，改为可读错误
        logger.warning("平台数据查询失败：%s", exc, exc_info=True)
        return _dumps(
            {
                "target": resolved,
                "error": f"查询失败：{type(exc).__name__}: {exc}",
                "hint": "请确认筛选条件后重试；若持续失败请联系管理员检查数据库连接",
            }
        )

    return _dumps(payload)


@tool(QUERY_TOOL_NAME)
def query_platform(
    target: str,
    keyword: str = "",
    project: str = "",
    module_id: int = 0,
    status: str = "",
    priority: str = "",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    detail: bool = False,
) -> str:
    """查询测试平台自身的数据（只读），支持四类对象：

    - target="projects"：查询项目（编码、名称、是否启用、用例数、计划数）
    - target="modules"：查询项目下的用例模块树（须指定 project）
    - target="testcases"：查询用例（可按项目、模块、优先级、状态、关键字筛选）
    - target="plans"：查询测试计划（含计划用例数与执行结果统计）

    何时使用:
    - 需要了解平台里有哪些项目 / 用例模块 / 用例 / 测试计划时
    - 需要按关键字、状态等条件检索用例或计划，或统计数量、查看执行结果时
    - 编写、评审、整理用例之前，需要先看已有用例与模块结构时

    何时不用:
    - 新增 / 修改 / 删除平台数据，或执行测试计划（本工具只读，请引导用户到平台页面操作）
    - 查看用例执行日志、定时任务等平台其它数据

    Args:
        target: 查询对象，取 projects / modules / testcases / plans，也接受中文别名（项目/模块/用例/计划）。
        keyword: 关键字模糊搜索。项目匹配名称、编码；模块匹配名称、编码、模块路径；用例匹配标题、模块名；计划匹配名称、说明。
        project: 限定项目，可填项目 ID 或项目编码（如 "DEMO"）。modules 必填；testcases / plans 留空表示不限项目；projects 填了则精确定位该项目。
        module_id: 模块 ID，仅 modules / testcases 有效；modules 返回该模块及其子模块，testcases 只返回该模块（含子模块）下的用例。
        status: 状态筛选。projects 取 active / inactive；testcases 取 draft / reviewed / archived；plans 取 not_started / in_progress / completed。留空不过滤。
        priority: 优先级筛选，仅 testcases 有效，取 P0 / P1 / P2 / P3。
        page: 页码，从 1 开始，默认 1。
        page_size: 每页条数，默认 20，最大 100。
        detail: 是否返回用例明细字段，仅 testcases 有效；为 true 时额外返回前置条件、步骤、预期结果、来源。

    返回:
        一段 JSON 文本：{target, filters, total, page, page_size, total_pages, returned, items}；
        模块 / 用例 / 计划查询会附带 resolved_project；命中为空或未取完时附带 hint。
        查询失败时返回 {target, error, hint?}，不抛异常。
    """
    return _execute(
        target=target,
        keyword=keyword,
        project=project,
        module_id=module_id,
        status=status,
        priority=priority,
        page=page,
        page_size=page_size,
        detail=detail,
    )
