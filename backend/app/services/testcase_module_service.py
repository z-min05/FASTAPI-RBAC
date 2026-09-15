"""用例模块服务

职责：
- 项目内多级模块树的增删改查
- 模块路径推导（祖先 code 链 → 相对路径，如 device/test_comm_log）
- 模块名称/code/层级变更后重算子树下用例的 module 与 module_code
- 向用例服务提供「末级模块」校验、按名称链查找等能力

约定（详见 docs/用例模块管理功能设计.md）：
- 末级 = 没有任何子节点；只有末级模块才能挂用例
- 模块 code 一律必填，为磁盘上的目录名或文件名
- 末级模块的 code 必须以 test_ 开头（校验时机在创建/编辑用例）
- 改名/移动只重算数据库路径，不搬迁磁盘文件
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.project import Project
from app.models.testcase import TestCase
from app.models.testcase_module import TestCaseModule
from app.repositories.project_repo import ProjectRepository
from app.repositories.testcase_module_repo import TestCaseModuleRepository
from app.schemas.testcase_module import TestCaseModuleCreate, TestCaseModuleUpdate
from app.services.auto_file_service import (
    ALLOW_MODULE_DIR_PATTERN,
    TEST_FILE_CODE_PATTERN,
)

# 祖先链回溯深度上限，防止脏数据造成的环路导致死循环
MAX_DEPTH = 32
# 子树遍历节点数上限（防御性）
MAX_SUBTREE_NODES = 100_000


def compute_module_path(
    code_by_id: dict[int, str],
    parent_by_id: dict[int, int | None],
    node_id: int,
) -> str:
    """由祖先链推导模块相对路径，如 'device/test_comm_log'

    code_by_id / parent_by_id 需覆盖同一项目下所有节点。
    遇到缺失节点或层级超过 MAX_DEPTH 时停止回溯，返回已收集的部分。
    """
    parts: list[str] = []
    current: int | None = node_id
    depth = 0
    while current is not None and depth < MAX_DEPTH:
        code = code_by_id.get(current)
        if not code:
            break
        parts.append(code)
        current = parent_by_id.get(current)
        depth += 1
    parts.reverse()
    return "/".join(parts)


def collect_subtree_ids(
    children_map: dict[int | None, list[int]], root_id: int
) -> list[int]:
    """收集以 root_id 为根的子树节点 id（含自身）"""
    collected: list[int] = []
    stack = [root_id]
    while stack and len(collected) < MAX_SUBTREE_NODES:
        current = stack.pop()
        collected.append(current)
        stack.extend(children_map.get(current, []))
    return collected


def build_index(
    nodes: list[TestCaseModule],
) -> tuple[dict[int, str], dict[int, int | None], dict[int | None, list[int]]]:
    """构造 code / parent / children 三个索引"""
    code_by_id = {n.id: n.code for n in nodes}
    parent_by_id = {n.id: n.parent_id for n in nodes}
    children_map: dict[int | None, list[int]] = {}
    for n in nodes:
        children_map.setdefault(n.parent_id, []).append(n.id)
    return code_by_id, parent_by_id, children_map


class TestCaseModuleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TestCaseModuleRepository(db)
        self.project_repo = ProjectRepository(db)

    # ---------- 读取 ----------

    async def get_tree(self, project_id: int) -> list[dict]:
        """取项目下的完整模块树（含 is_leaf / module_path / 用例数）"""
        await self._ensure_project_exists(project_id)
        nodes = await self.repo.get_by_project(project_id)
        return await self._assemble_tree(nodes)

    async def get_module(self, module_id: int) -> TestCaseModule:
        node = await self.repo.get_by_id(module_id)
        if not node:
            raise NotFoundException("模块不存在")
        return node

    async def get_module_detail(self, module_id: int) -> dict:
        node = await self.get_module(module_id)
        nodes = await self.repo.get_by_project(node.project_id)
        code_by_id, parent_by_id, children_map = build_index(nodes)
        subtree_ids = collect_subtree_ids(children_map, node.id)
        counts = await self.repo.case_counts(subtree_ids)
        return self._to_dict(
            node,
            code_by_id,
            parent_by_id,
            is_leaf=not children_map.get(node.id),
            case_count=counts.get(node.id, 0),
            total_case_count=sum(counts.values()),
        )

    async def _assemble_tree(self, nodes: list[TestCaseModule]) -> list[dict]:
        if not nodes:
            return []
        code_by_id, parent_by_id, children_map = build_index(nodes)
        node_by_id = {n.id: n for n in nodes}
        counts = await self.repo.case_counts(list(node_by_id.keys()))

        def build(node: TestCaseModule, depth: int = 0) -> dict:
            child_ids = [] if depth >= MAX_DEPTH else children_map.get(node.id, [])
            children = [
                build(node_by_id[cid], depth + 1)
                for cid in child_ids
                if cid in node_by_id
            ]
            own = counts.get(node.id, 0)
            item = self._to_dict(
                node,
                code_by_id,
                parent_by_id,
                is_leaf=not child_ids,
                case_count=own,
                total_case_count=own + sum(c["total_case_count"] for c in children),
            )
            item["children"] = children
            return item

        # 父节点不在本项目节点集合中的视为顶级，兜底数据异常时不丢节点
        root_ids = [
            n.id for n in nodes if n.parent_id is None or n.parent_id not in node_by_id
        ]
        return [build(node_by_id[rid]) for rid in root_ids]

    @staticmethod
    def _to_dict(
        node: TestCaseModule,
        code_by_id: dict[int, str],
        parent_by_id: dict[int, int | None],
        is_leaf: bool,
        case_count: int,
        total_case_count: int,
    ) -> dict:
        return {
            "id": node.id,
            "project_id": node.project_id,
            "parent_id": node.parent_id,
            "name": node.name,
            "code": node.code,
            "description": node.description,
            "sort": node.sort,
            "is_leaf": is_leaf,
            "module_path": compute_module_path(code_by_id, parent_by_id, node.id),
            "case_count": case_count,
            "total_case_count": total_case_count,
            "created_at": node.created_at,
            "updated_at": node.updated_at,
        }

    # ---------- 写操作 ----------

    async def create_module(self, data: TestCaseModuleCreate) -> TestCaseModule:
        await self._ensure_project_exists(data.project_id)
        name = (data.name or "").strip()
        code = (data.code or "").strip()
        self._validate_name(name)
        self._validate_code(code)

        if data.parent_id is not None:
            parent = await self.get_module(data.parent_id)
            if parent.project_id != data.project_id:
                raise BadRequestException("上级模块不属于该项目")
            # 父节点将变成非末级，不能再挂用例
            await self._ensure_parent_can_group(parent.id)

        await self._ensure_sibling_unique(data.project_id, data.parent_id, name, code)

        node = TestCaseModule(
            project_id=data.project_id,
            parent_id=data.parent_id,
            name=name,
            code=code,
            description=data.description,
            sort=data.sort or 0,
        )
        return await self.repo.create(node)

    async def update_module(
        self, module_id: int, data: TestCaseModuleUpdate
    ) -> TestCaseModule:
        node = await self.get_module(module_id)
        update_data = data.model_dump(exclude_unset=True)

        new_name = (update_data.get("name") or node.name).strip()
        new_code = (update_data.get("code") or node.code).strip()
        new_parent_id = update_data.get("parent_id", node.parent_id)

        self._validate_name(new_name)
        self._validate_code(new_code)

        nodes = await self.repo.get_by_project(node.project_id)
        _, _, children_map = build_index(nodes)
        is_leaf = not children_map.get(node.id)

        if new_parent_id != node.parent_id and new_parent_id is not None:
            parent = next((n for n in nodes if n.id == new_parent_id), None)
            if parent is None:
                raise BadRequestException("上级模块不存在")
            if parent.project_id != node.project_id:
                raise BadRequestException("上级模块不属于该项目")
            if new_parent_id in collect_subtree_ids(children_map, node.id):
                raise BadRequestException("不能移动到自身的子模块下")
            await self._ensure_parent_can_group(parent.id)

        # 末级且已挂用例的模块，code 必须仍是合法的 pytest 文件名
        case_count = await self.repo.count_cases(node.id)
        if is_leaf and case_count and not TEST_FILE_CODE_PATTERN.fullmatch(new_code):
            raise ConflictException(
                f"该模块下已有 {case_count} 条用例，文件名必须以 test_ 开头"
            )

        await self._ensure_sibling_unique(
            node.project_id, new_parent_id, new_name, new_code, exclude_id=node.id
        )

        path_changed = new_code != node.code or new_parent_id != node.parent_id
        name_changed = new_name != node.name

        node.name = new_name
        node.code = new_code
        node.parent_id = new_parent_id
        if "description" in update_data:
            node.description = update_data["description"]
        if update_data.get("sort") is not None:
            node.sort = update_data["sort"]
        await self.db.flush()

        if path_changed or name_changed:
            await self._resync_subtree_cases(node)
        return node

    async def delete_module(self, module_id: int) -> None:
        node = await self.get_module(module_id)
        child_count = await self.repo.count_children(node.id)
        if child_count:
            raise ConflictException(f"该模块下还有 {child_count} 个子模块，请先删除子模块")
        case_count = await self.repo.count_cases(node.id)
        if case_count:
            raise ConflictException(f"该模块下还有 {case_count} 条用例，请先移走用例")
        await self.repo.delete(node.id)

    async def _resync_subtree_cases(self, root: TestCaseModule) -> int:
        """模块改名/移动后重算子树下所有用例的 module 与 module_code

        只改数据库，不搬迁磁盘文件：旧路径下的文件保留，由用户手动清理。
        """
        nodes = await self.repo.get_by_project(root.project_id)
        code_by_id, parent_by_id, children_map = build_index(nodes)
        name_by_id = {n.id: n.name for n in nodes}

        affected = 0
        for module_id in collect_subtree_ids(children_map, root.id):
            new_path = compute_module_path(code_by_id, parent_by_id, module_id)
            new_name = name_by_id.get(module_id)
            if not new_path or not new_name:
                continue
            result = await self.db.execute(
                update(TestCase)
                .where(TestCase.module_id == module_id)
                .values(module=new_name, module_code=new_path)
            )
            affected += result.rowcount or 0
        await self.db.flush()
        return affected

    # ---------- 供用例服务 / 同步服务复用的能力 ----------

    async def require_leaf_module(
        self, project_id: int, module_id: int
    ) -> tuple[TestCaseModule, str]:
        """校验模块可挂用例：存在、同项目、无子节点、code 为合法 pytest 文件名

        返回 (末级模块, 模块相对路径)
        """
        node = await self.get_module(module_id)
        if node.project_id != project_id:
            raise BadRequestException("模块不属于该项目")
        if await self.repo.count_children(node.id):
            raise BadRequestException("只能选择末级模块")
        if not TEST_FILE_CODE_PATTERN.fullmatch(node.code or ""):
            raise BadRequestException(
                "该模块将作为 pytest 文件使用，请把目录名改为 test_ 开头，如 test_device"
            )
        return node, await self.get_module_path(node)

    async def get_module_path(self, node: TestCaseModule) -> str:
        nodes = await self.repo.get_by_project(node.project_id)
        code_by_id, parent_by_id, _ = build_index(nodes)
        return compute_module_path(code_by_id, parent_by_id, node.id)

    async def collect_subtree_module_ids(
        self, project_id: int, module_id: int
    ) -> list[int]:
        nodes = await self.repo.get_by_project(project_id)
        _, _, children_map = build_index(nodes)
        return collect_subtree_ids(children_map, module_id)

    async def get_name_path_map(self, project_ids: list[int]) -> dict[int, str]:
        """批量取 module_id -> 模块名称链（如 设备管理/通信日志），CSV 导出用"""
        ids = list(set(project_ids))
        if not ids:
            return {}
        stmt = select(TestCaseModule).where(TestCaseModule.project_id.in_(ids))
        nodes = list((await self.db.execute(stmt)).scalars().all())
        name_by_id = {n.id: n.name for n in nodes}
        parent_by_id = {n.id: n.parent_id for n in nodes}
        return {
            n.id: compute_module_path(name_by_id, parent_by_id, n.id) for n in nodes
        }

    async def find_leaf_by_name_path(
        self, project_id: int, name_path: str
    ) -> TestCaseModule:
        """按「名称链」（如 设备管理/通信日志）查找末级模块

        用于 CSV 导入；找不到或命中非末级都抛 BadRequestException。
        """
        parts = [p.strip() for p in (name_path or "").split("/") if p.strip()]
        if not parts:
            raise BadRequestException("模块路径不能为空")

        nodes = await self.repo.get_by_project(project_id)
        parent_id: int | None = None
        current: TestCaseModule | None = None
        for part in parts:
            matched = [n for n in nodes if n.parent_id == parent_id and n.name == part]
            if len(matched) != 1:
                raise BadRequestException(
                    f"模块路径不存在：{name_path}，请先在模块树中创建"
                )
            current = matched[0]
            parent_id = current.id

        if current is None:
            raise BadRequestException(f"模块路径不存在：{name_path}，请先在模块树中创建")
        if any(n.parent_id == current.id for n in nodes):
            raise BadRequestException(
                f"模块路径指向的是分组目录，用例只能建在末级模块下：{name_path}"
            )
        return current

    # ---------- 内部校验 ----------

    async def _ensure_project_exists(self, project_id: int) -> Project:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise BadRequestException("项目不存在")
        return project

    async def _ensure_parent_can_group(self, parent_id: int) -> None:
        """父节点将变为非末级：它下面不能再有用例"""
        case_count = await self.repo.count_cases(parent_id)
        if case_count:
            raise ConflictException(
                f"该模块下还有 {case_count} 条用例，请先移走用例再把它作为分组目录"
            )

    async def _ensure_sibling_unique(
        self,
        project_id: int,
        parent_id: int | None,
        name: str,
        code: str,
        exclude_id: int | None = None,
    ) -> None:
        if await self.repo.exists_sibling(
            project_id, parent_id, name=name, exclude_id=exclude_id
        ):
            raise ConflictException(f"同级已存在同名模块：{name}")
        if await self.repo.exists_sibling(
            project_id, parent_id, code=code, exclude_id=exclude_id
        ):
            raise ConflictException(f"同级已存在相同目录名：{code}")

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name:
            raise BadRequestException("模块名称不能为空")
        if len(name) > 50:
            raise BadRequestException("模块名称长度不能超过 50")
        if "/" in name:
            raise BadRequestException("模块名称不能包含 /")

    @staticmethod
    def _validate_code(code: str) -> None:
        if not code:
            raise BadRequestException("目录名/文件名不能为空")
        if not ALLOW_MODULE_DIR_PATTERN.fullmatch(code):
            raise BadRequestException(
                "目录名/文件名格式不合法：只允许字母、数字、下划线、短横线，长度 1-100"
            )
