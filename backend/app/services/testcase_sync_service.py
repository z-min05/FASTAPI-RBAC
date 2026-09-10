"""用例同步服务

职责：
- 从项目的自动化根路径（pytest tests 目录）反向扫描测试文件
- 映射：文件名(去 .py) → module_code；顶层 test_* 函数名 → case_code；@allure.title → title
- 只新增不修改：同项目下 (module_code, case_code) 已存在则跳过
- 异步下发：接口侧调用 dispatch_project_sync 后立即返回，后台任务只记日志

约定：
- 不导入、不执行被测代码，仅用 ast 静态解析
- 同步过程不调用 generate_automation_file，绝不改写任何 .py 文件
- 已存在判定与创建/编辑用例一致：同项目下 (module_code, case_code) 唯一
"""
import asyncio
import ast
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.exceptions import BadRequestException
from app.models.project import Project
from app.models.testcase import TestCase
from app.services.auto_file_service import validate_codes
from app.utils.logger import logger

# 扫描时忽略的目录（含隐藏目录）
_EXCLUDE_DIRS = {"__pycache__", "venv", ".venv", "node_modules", ".git", "site-packages"}
# 单文件大小上限（2MB），超过则跳过，避免误读大文件
_MAX_FILE_BYTES = 2 * 1024 * 1024
# 同步入库时的默认值（详见设计文档 §1.3）
_DEFAULT_SOURCE = "自动同步"
_DEFAULT_MODULE_FALLBACK = "自动同步"
# 后台任务强引用，避免被 GC 回收
_running_tasks: set = set()


# ---------- 扫描与解析 ----------

def _extract_allure_title(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """提取 @allure.title("...") 的字符串参数，取不到返回 None"""
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        func = decorator.func
        if not (isinstance(func, ast.Attribute) and func.attr == "title"):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id == "allure"):
            continue
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            title = decorator.args[0].value
            if isinstance(title, str) and title.strip():
                return title.strip()
    return None


def _iter_test_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """取模块顶层的 test_* 函数（含 async），class 内方法不在本轮同步范围内"""
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    ]


def _should_skip_dir(rel_parts: tuple[str, ...]) -> bool:
    return any(part.startswith(".") or part in _EXCLUDE_DIRS for part in rel_parts)


def scan_test_functions(root: Path) -> tuple[list[dict], list[str]]:
    """扫描根路径下所有 pytest 测试文件的顶层测试函数

    返回 (items, failures)：
    - items: [{file_name, module_code, case_code, title}]
    - failures: [原因描述]（文件读不了 / 语法错误 / 文件名不合法等，仅记日志）
    """
    items: list[dict] = []
    failures: list[str] = []

    try:
        files = sorted(root.rglob("test_*.py"))
    except OSError as e:
        return [], [f"扫描目录失败: {e}"]

    for file_path in files:
        try:
            rel_parts = file_path.relative_to(root).parts[:-1]
        except ValueError:
            continue
        if _should_skip_dir(rel_parts):
            continue
        if file_path.name == "conftest.py":
            continue

        module_code = file_path.stem
        try:
            validate_codes(module_code, None)
        except BadRequestException as e:
            failures.append(f"{file_path}: {e}")
            continue

        try:
            if file_path.stat().st_size > _MAX_FILE_BYTES:
                failures.append(f"{file_path}: 文件超过 {_MAX_FILE_BYTES // 1024 // 1024}MB，已跳过")
                continue
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            failures.append(f"{file_path}: 读取失败（{e}）")
            continue

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            failures.append(f"{file_path}: 语法错误（第 {e.lineno} 行）")
            continue

        for node in _iter_test_functions(tree):
            case_code = node.name
            try:
                validate_codes(None, case_code)
            except BadRequestException as e:
                failures.append(f"{file_path}::{case_code}: {e}")
                continue
            items.append({
                "file_name": file_path.name,
                "module_code": module_code,
                "case_code": case_code,
                "title": _extract_allure_title(node) or case_code,
            })

    return items, failures


# ---------- 校验与下发 ----------

async def ensure_sync_ready(db: AsyncSession, project_id: int) -> Project:
    """同步前置校验：项目存在且启用、已配置可用的自动化根路径"""
    project = await db.get(Project, project_id)
    if not project:
        raise BadRequestException("项目不存在")
    if not project.is_active:
        raise BadRequestException("项目已停用，无法同步用例")
    if not project.auto_root_path:
        raise BadRequestException("该项目未配置自动化根路径，无法同步")
    root = Path(project.auto_root_path)
    if not root.exists():
        raise BadRequestException(f"自动化根路径不存在: {project.auto_root_path}")
    if not root.is_dir():
        raise BadRequestException(f"自动化根路径必须是目录: {project.auto_root_path}")
    return project


def dispatch_project_sync(project_id: int) -> None:
    """下发后台同步任务（保持强引用，避免被 GC 回收）"""
    task = asyncio.create_task(sync_project_testcases(project_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def sync_project_testcases(project_id: int) -> None:
    """后台任务：扫描并入库（只新增，已存在/编码不合法跳过），结果仅记日志"""
    try:
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, project_id)
            if not project or not project.auto_root_path:
                logger.warning(f"用例同步跳过：项目 {project_id} 不存在或未配置自动化根路径")
                return
            root = Path(project.auto_root_path)
            items, failures = await asyncio.to_thread(scan_test_functions, root)

            created = skipped_exists = skipped_invalid = 0
            for item in items:
                try:
                    validate_codes(item["module_code"], item["case_code"])
                except BadRequestException as e:
                    skipped_invalid += 1
                    failures.append(f"{item['file_name']}::{item['case_code']}: {e}")
                    continue

                exists = (await db.execute(
                    select(TestCase.id).where(
                        TestCase.project_id == project_id,
                        TestCase.module_code == item["module_code"],
                        TestCase.case_code == item["case_code"],
                    ).limit(1)
                )).scalar()
                if exists is not None:
                    skipped_exists += 1
                    continue

                db.add(TestCase(
                    project_id=project_id,
                    title=item["title"],
                    module=item["module_code"] or _DEFAULT_MODULE_FALLBACK,
                    priority="P1",
                    case_type="function",
                    source=_DEFAULT_SOURCE,
                    precondition=None,
                    steps=None,
                    expected_result="待补充",
                    status="draft",
                    tags=None,
                    module_code=item["module_code"],
                    case_code=item["case_code"],
                ))
                created += 1

            await db.commit()
            logger.info(
                f"用例同步完成 project={project_id} 路径={root} "
                f"新增={created} 已存在={skipped_exists} 编码不合法={skipped_invalid} 解析失败={len(failures)}"
            )
            for reason in failures[:20]:
                logger.warning(f"用例同步跳过: {reason}")
    except Exception as e:
        logger.exception(f"用例同步失败 project={project_id}: {e}")
