"""用例同步服务

职责：
- 从项目的自动化根路径（pytest tests 目录）反向扫描测试文件
- 映射：相对目录链 → 分组模块（逐级 get_or_create），文件名(去 .py) → 末级模块，
  顶层 test_* 函数名 → case_code；@allure.title → title
- 只新增不修改：同项目同一末级模块下 case_code 已存在则跳过
- 异步下发：接口侧调用 dispatch_project_sync 后立即返回，后台任务只记日志

约定：
- 不导入、不执行被测代码，仅用 ast 静态解析
- 同步过程不调用 generate_automation_file，绝不改写任何 .py 文件
- 已存在判定与创建/编辑用例一致：同项目同一末级模块下 case_code 唯一
- 同步建出的节点 name 取 code 原文（磁盘上的英文名），用户可后续改成中文展示名
"""
import asyncio
import ast
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.exceptions import BadRequestException
from app.models.project import Project
from app.models.testcase import TestCase
from app.models.testcase_module import TestCaseModule
from app.services.auto_file_service import ALLOW_MODULE_DIR_PATTERN, validate_codes
from app.utils.logger import logger

# 扫描时忽略的目录（含隐藏目录）
_EXCLUDE_DIRS = {"__pycache__", "venv", ".venv", "node_modules", ".git", "site-packages"}
# 单文件大小上限（2MB），超过则跳过，避免误读大文件
_MAX_FILE_BYTES = 2 * 1024 * 1024
# 同步入库时的默认值（详见设计文档 §1.3）
_DEFAULT_SOURCE = "自动同步"
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
    - items: [{rel_dir, file_stem, module_code, case_code, title}]
      rel_dir 为相对 tests 的目录链（不含文件名），module_code 为相对路径（不含 .py）
    - failures: [原因描述]（文件读不了 / 语法错误 / 目录名或编码不合法等，仅记日志）
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

        # 目录名会成为模块节点，字符集不合法则整条跳过（不建节点）
        bad_dir = next(
            (p for p in rel_parts if not ALLOW_MODULE_DIR_PATTERN.fullmatch(p)), None
        )
        if bad_dir is not None:
            failures.append(f"{file_path}: 目录名不合法，已跳过（{bad_dir}）")
            continue

        module_code = "/".join([*rel_parts, file_path.stem])
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
                "rel_dir": rel_parts,
                "file_stem": file_path.stem,
                "module_code": module_code,
                "case_code": case_code,
                "title": _extract_allure_title(node) or case_code,
            })

    return items, failures


# ---------- 自动建树 ----------

async def _load_module_cache(
    db: AsyncSession, project_id: int
) -> dict[tuple[int | None, str], TestCaseModule]:
    """加载项目下已有模块，索引为 (parent_id, code)"""
    stmt = select(TestCaseModule).where(TestCaseModule.project_id == project_id)
    nodes = list((await db.execute(stmt)).scalars().all())
    return {(n.parent_id, n.code): n for n in nodes}


class _ModuleTreeBuilder:
    """按磁盘目录层级自动建树（只新增，不改名、不移动）

    - 目录节点与末级文件节点的 name 均取 code 原文，用户可在模块树里改成中文
    - 若某节点下已挂用例、又需要它充当目录，则跳过该分支并记录原因
    """

    def __init__(
        self, db: AsyncSession, project_id: int, cache: dict[tuple[int | None, str], TestCaseModule]
    ):
        self.db = db
        self.project_id = project_id
        self.cache = cache
        self.failures: list[str] = []
        self._groupable: set[int] = set()

    async def ensure_leaf(
        self, rel_dir: tuple[str, ...], file_stem: str
    ) -> TestCaseModule | None:
        parent_id: int | None = None
        for part in rel_dir:
            node = await self._get_or_create(parent_id, part)
            if node is None:
                return None
            parent_id = node.id
        return await self._get_or_create(parent_id, file_stem)

    async def _get_or_create(
        self, parent_id: int | None, code: str
    ) -> TestCaseModule | None:
        node = self.cache.get((parent_id, code))
        if node is not None:
            return node
        if parent_id is not None and not await self._can_group(parent_id):
            return None
        node = TestCaseModule(
            project_id=self.project_id,
            parent_id=parent_id,
            name=code,
            code=code,
            sort=0,
        )
        self.db.add(node)
        await self.db.flush()
        self.cache[(parent_id, code)] = node
        return node

    async def _can_group(self, module_id: int) -> bool:
        """父节点将变为非末级：它下面不能再有用例"""
        if module_id in self._groupable:
            return True
        count = (await self.db.execute(
            select(func.count()).select_from(TestCase).where(TestCase.module_id == module_id)
        )).scalar() or 0
        if count:
            self.failures.append(
                f"模块 id={module_id} 下已有 {count} 条用例，无法作为目录容纳子模块，"
                "该目录下的文件已跳过"
            )
            return False
        self._groupable.add(module_id)
        return True


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

            cache = await _load_module_cache(db, project_id)
            builder = _ModuleTreeBuilder(db, project_id, cache)

            created = skipped_exists = skipped_invalid = 0
            for item in items:
                try:
                    validate_codes(item["module_code"], item["case_code"])
                except BadRequestException as e:
                    skipped_invalid += 1
                    failures.append(f"{item['module_code']}::{item['case_code']}: {e}")
                    continue

                # 目录 → 分组节点，文件 → 末级节点（逐级 get_or_create）
                node = await builder.ensure_leaf(item["rel_dir"], item["file_stem"])
                if node is None:
                    skipped_invalid += 1
                    continue

                exists = (await db.execute(
                    select(TestCase.id).where(
                        TestCase.project_id == project_id,
                        TestCase.module_id == node.id,
                        TestCase.case_code == item["case_code"],
                    ).limit(1)
                )).scalar()
                if exists is not None:
                    skipped_exists += 1
                    continue

                db.add(TestCase(
                    project_id=project_id,
                    module_id=node.id,
                    module=node.name,
                    module_code=item["module_code"],
                    title=item["title"],
                    priority="P1",
                    case_type="function",
                    source=_DEFAULT_SOURCE,
                    precondition=None,
                    steps=None,
                    expected_result="待补充",
                    status="draft",
                    tags=None,
                    case_code=item["case_code"],
                ))
                created += 1

            failures.extend(builder.failures)
            await db.commit()
            logger.info(
                f"用例同步完成 project={project_id} 路径={root} "
                f"新增={created} 已存在={skipped_exists} 编码不合法={skipped_invalid} 解析失败={len(failures)}"
            )
            for reason in failures[:20]:
                logger.warning(f"用例同步跳过: {reason}")
    except Exception as e:
        logger.exception(f"用例同步失败 project={project_id}: {e}")
