"""自动化测试环境管理服务

目录布局（proj_root = Path(project.auto_root_path).parent）：

    {proj_root}/.env              生效环境文件（自动化框架读取的那个）
    {proj_root}/.envs/<name>.env  环境快照（多套环境并存）
    {proj_root}/.envs/.backup/    切换/保存生效环境前的自动备份

约定：
- 内容以文件为权威；数据库 project_envs 只存备注/创建人等元信息，不存内容
- 「当前生效环境」由内容比对判定（归一化后相等），不维护指针文件
- 所有环境文件路径 resolve 后必须落在 .envs 目录内，防止目录穿越
- 写文件一律「临时文件 + os.replace」原子替换，避免留下半截文件
"""
import asyncio
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.plan import TestPlan
from app.models.plan_testcase import PlanTestCase
from app.models.project import Project
from app.models.project_env import ProjectEnv
from app.models.testcase import TestCase
from app.services.auto_exec_service import format_conflict_titles

# 环境名：字母数字开头，允许下划线/中划线；不允许点、空格、中文，杜绝路径穿越
ENV_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
# KEY=VALUE（兼容 export KEY=VALUE）
_KV_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
# 疑似敏感键名：API_KEY / SECRET_KEY / PASSWORD / TOKEN / CREDENTIALS ...
_SENSITIVE_RE = re.compile(
    r"(?:^|_)(PASSWORD|PASSWD|PWD|SECRET|TOKEN|KEY|CREDENTIALS?)(?:_|$)", re.IGNORECASE
)

# 进程内按项目串行化「应用/保存」操作（多 worker 下不做分布式锁，切换是低频人工操作）
_env_locks: dict[int, asyncio.Lock] = {}


def _project_lock(project_id: int) -> asyncio.Lock:
    lock = _env_locks.get(project_id)
    if lock is None:
        lock = asyncio.Lock()
        _env_locks[project_id] = lock
    return lock


# ---------- 内容解析工具 ----------

def _to_lf(text: str) -> str:
    """统一换行为 LF"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_content(text: str) -> str:
    """归一化后用于比对：去行尾空白、统一换行、去首尾空行"""
    lines = [ln.rstrip() for ln in _to_lf(text).split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def parse_env_lines(text: str) -> tuple[list[dict], list[str]]:
    """逐行解析环境文件，返回 (行列表, 告警列表)

    行类型：comment（# / ; 开头）、blank（空行）、kv（KEY=VALUE）、raw（其它）
    非标准行不阻塞保存，仅给出告警（框架可能支持扩展语法）。
    """
    raw_lines = _to_lf(text).split("\n")
    # split 会在末尾换行处多出一个空元素，去掉以便行号与真实文件一致
    if raw_lines and raw_lines[-1] == "":
        raw_lines.pop()

    lines: list[dict] = []
    warnings: list[str] = []
    for no, raw in enumerate(raw_lines, start=1):
        stripped = raw.strip()
        if not stripped:
            lines.append({"no": no, "type": "blank", "raw": raw})
            continue
        if stripped.startswith("#") or stripped.startswith(";"):
            lines.append({"no": no, "type": "comment", "raw": raw})
            continue
        matched = _KV_RE.match(raw)
        if matched:
            key, value = matched.group(1), matched.group(2)
            lines.append({
                "no": no,
                "type": "kv",
                "raw": raw,
                "key": key,
                "value": value,
                "sensitive": bool(_SENSITIVE_RE.search(key)),
            })
        else:
            lines.append({"no": no, "type": "raw", "raw": raw})
            warnings.append(f"第 {no} 行不是标准 KEY=VALUE 格式，已按原文保留")
    return lines, warnings


def kv_map(text: str) -> dict[str, str]:
    """取键值映射（同名键后出现的覆盖先出现的）"""
    lines, _ = parse_env_lines(text)
    return {ln["key"]: ln["value"] for ln in lines if ln["type"] == "kv"}


async def project_has_running_cases(db: AsyncSession, project_id: int) -> list[str]:
    """项目下是否存在执行中的用例（跨计划），返回去重后的用例标题"""
    rows = (
        await db.execute(
            select(TestCase.title)
            .join(PlanTestCase, PlanTestCase.testcase_id == TestCase.id)
            .join(TestPlan, TestPlan.id == PlanTestCase.plan_id)
            .where(
                TestPlan.project_id == project_id,
                PlanTestCase.result == "running",
            )
        )
    ).scalars().all()
    titles: list[str] = []
    for title in rows:
        if title not in titles:
            titles.append(title)
    return titles


# ---------- 服务 ----------

class ProjectEnvService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- 基础路径 ----------

    async def _get_project(self, project_id: int) -> Project:
        project = await self.db.get(Project, project_id)
        if not project:
            raise NotFoundException("项目不存在")
        return project

    def _resolve_root(self, project: Project) -> Path:
        """项目根目录 = auto_root_path(tests 目录) 的父目录"""
        raw = (project.auto_root_path or "").strip()
        if not raw:
            raise BadRequestException("该项目尚未生成自动化根路径，请先上传代码包并完成初始化")
        tests_dir = Path(raw)
        if not tests_dir.is_dir():
            raise BadRequestException(f"自动化根路径不存在或不是目录: {raw}")
        root = tests_dir.resolve().parent
        if root == Path(root.anchor):
            raise BadRequestException(f"项目目录不合法: {root}")
        return root

    def _safe_env_path(self, root: Path, name: str) -> Path:
        if not ENV_NAME_RE.fullmatch(name or ""):
            raise BadRequestException(
                "环境名不合法：仅允许字母、数字、下划线、中划线，且以字母或数字开头"
            )
        base = (root / ".envs").resolve()
        target = base / f"{name}.env"
        if target.parent != base:
            raise BadRequestException("环境路径不合法")
        return target

    def _ensure_envs_dir(self, root: Path) -> Path:
        envs_dir = root / ".envs"
        try:
            envs_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise BadRequestException(f"环境目录不可用: {envs_dir}（{e}）")
        return envs_dir

    def _list_env_files(self, root: Path) -> list[Path]:
        envs_dir = root / ".envs"
        if not envs_dir.is_dir():
            return []
        return sorted(
            (
                p for p in envs_dir.glob("*.env")
                if p.is_file() and not p.name.startswith(".")
            ),
            key=lambda p: p.stem.lower(),
        )

    # ---------- 文件读写 ----------

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            raw = path.read_bytes()
        except OSError as e:
            raise BadRequestException(f"环境文件读取失败: {path.name}（{e}）")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            raise BadRequestException(f"环境文件不是 UTF-8 编码，无法在平台编辑: {path.name}")

    def _check_size(self, content: str) -> None:
        limit = settings.PROJECT_ENV_MAX_KB * 1024
        size = len(content.encode("utf-8"))
        if size > limit:
            raise BadRequestException(
                f"内容大小 {size / 1024:.1f}KB 超过上限 {settings.PROJECT_ENV_MAX_KB}KB"
            )

    def _write_atomic(self, path: Path, content: str) -> None:
        """临时文件 + os.replace 原子替换，避免写入中断留下半截文件"""
        content = _to_lf(content)
        self._check_size(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            os.replace(tmp, path)
        except OSError as e:
            raise BadRequestException(f"环境文件写入失败: {path.name}（{e}）")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def _backup_active_file(self, root: Path) -> str | None:
        """备份当前 .env，并清理超出保留份数的旧备份"""
        active = root / ".env"
        if not active.is_file():
            return None
        backup_dir = root / ".envs" / ".backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        name = f".env.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        try:
            shutil.copyfile(active, backup_dir / name)
        except OSError as e:
            raise BadRequestException(f"备份当前 .env 失败（{e}）")
        keep = max(1, settings.PROJECT_ENV_BACKUP_KEEP)
        for old in sorted(backup_dir.glob(".env.*.bak"))[:-keep]:
            old.unlink(missing_ok=True)
        return name

    # ---------- 生效环境判定 ----------

    def _detect_active(self, root: Path, files: list[Path]) -> tuple[str | None, list[str]]:
        """返回 (当前生效环境名 | None, 内容完全相同的环境名列表)"""
        active_file = root / ".env"
        if not active_file.is_file():
            return None, []
        try:
            target = normalize_content(self._read_text(active_file))
        except BadRequestException:
            return None, []
        same: list[str] = []
        for path in files:
            try:
                if normalize_content(self._read_text(path)) == target:
                    same.append(path.stem)
            except BadRequestException:
                continue
        if not same:
            return None, []
        return same[0], same

    # ---------- 元信息（DB） ----------

    async def _get_meta(self, project_id: int, name: str) -> ProjectEnv | None:
        return (
            await self.db.execute(
                select(ProjectEnv).where(
                    ProjectEnv.project_id == project_id, ProjectEnv.name == name
                )
            )
        ).scalar_one_or_none()

    async def _upsert_meta(
        self, project_id: int, name: str, remark: str | None, actor_id: int | None
    ) -> None:
        row = await self._get_meta(project_id, name)
        if row:
            row.remark = remark
            if row.created_by is None and actor_id:
                row.created_by = actor_id
        else:
            self.db.add(
                ProjectEnv(
                    project_id=project_id, name=name, remark=remark, created_by=actor_id
                )
            )
        await self.db.commit()

    # ---------- 执行冲突 ----------

    async def _assert_no_running(self, project_id: int) -> None:
        titles = await project_has_running_cases(self.db, project_id)
        if titles:
            raise BadRequestException(
                "项目存在执行中的用例，无法修改生效环境："
                f"{format_conflict_titles(titles)}。请等待执行结束后再操作"
            )

    # ---------- 查询 ----------

    async def list_envs(self, project_id: int) -> dict:
        project = await self._get_project(project_id)
        root = self._resolve_root(project)
        files = self._list_env_files(root)
        active_name, duplicated = self._detect_active(root, files)

        meta_map: dict[str, ProjectEnv] = {}
        if files:
            rows = (
                await self.db.execute(
                    select(ProjectEnv).where(
                        ProjectEnv.project_id == project_id,
                        ProjectEnv.name.in_([f.stem for f in files]),
                    )
                )
            ).scalars().all()
            meta_map = {r.name: r for r in rows}

        items = []
        for path in files:
            meta = meta_map.get(path.stem)
            try:
                text = self._read_text(path)
                key_count = len(kv_map(text))
                size = len(text.encode("utf-8"))
            except BadRequestException:
                key_count, size = 0, 0
            items.append({
                "name": path.stem,
                "remark": meta.remark if meta else None,
                "created_by": meta.created_by if meta else None,
                "key_count": key_count,
                "size": size,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime),
                "is_active": path.stem == active_name,
                "external": meta is None,
            })

        has_active = (root / ".env").is_file()
        return {
            "project_root": str(root),
            "has_active_env_file": has_active,
            "active_env": active_name,
            "drifted": has_active and active_name is None,
            "duplicated": duplicated if len(duplicated) > 1 else [],
            "items": items,
        }

    async def get_env(self, project_id: int, name: str) -> dict:
        project = await self._get_project(project_id)
        root = self._resolve_root(project)
        path = self._safe_env_path(root, name)
        if not path.is_file():
            raise NotFoundException(f"环境不存在: {name}")
        meta = await self._get_meta(project_id, name)
        active_name, _ = self._detect_active(root, self._list_env_files(root))
        content = self._read_text(path)
        lines, warnings = parse_env_lines(content)
        return {
            "name": name,
            "exists": True,
            "content": content,
            "lines": lines,
            "warnings": warnings,
            "is_active": active_name == name,
            "remark": meta.remark if meta else None,
        }

    async def get_active_file(self, project_id: int) -> dict:
        project = await self._get_project(project_id)
        root = self._resolve_root(project)
        active_file = root / ".env"
        exists = active_file.is_file()
        content = self._read_text(active_file) if exists else ""
        lines, warnings = parse_env_lines(content)
        active_name, _ = self._detect_active(root, self._list_env_files(root))
        meta = await self._get_meta(project_id, active_name) if active_name else None
        return {
            "name": active_name,
            "exists": exists,
            "content": content,
            "lines": lines,
            "warnings": warnings,
            "is_active": active_name is not None,
            "remark": meta.remark if meta else None,
        }

    async def diff_envs(self, project_id: int, left: str, right: str) -> dict:
        """对比两个环境（用 "@active" 表示当前生效的 .env）"""
        project = await self._get_project(project_id)
        root = self._resolve_root(project)

        def _resolve(ref: str) -> tuple[str, Path]:
            if ref == "@active":
                return "@active", root / ".env"
            return ref, self._safe_env_path(root, ref)

        left_label, left_path = _resolve(left)
        right_label, right_path = _resolve(right)
        for label, path in ((left_label, left_path), (right_label, right_path)):
            if not path.is_file():
                raise NotFoundException(f"环境文件不存在: {label}")

        left_map = kv_map(self._read_text(left_path))
        right_map = kv_map(self._read_text(right_path))
        return {
            "left": left_label,
            "right": right_label,
            "added": [
                {"key": k, "right": v} for k, v in right_map.items() if k not in left_map
            ],
            "removed": [
                {"key": k, "left": v} for k, v in left_map.items() if k not in right_map
            ],
            "changed": [
                {"key": k, "left": left_map[k], "right": right_map[k]}
                for k, v in right_map.items()
                if k in left_map and left_map[k] != v
            ],
        }

    # ---------- 写入 ----------

    async def save_env(
        self, project_id: int, name: str, content: str, remark: str | None, actor_id: int | None
    ) -> dict:
        """保存环境快照；若它正是当前生效环境，同时把 .env 一起更新"""
        async with _project_lock(project_id):
            project = await self._get_project(project_id)
            root = self._resolve_root(project)
            path = self._safe_env_path(root, name)
            if not path.is_file():
                raise NotFoundException(f"环境不存在: {name}")

            active_name, _ = self._detect_active(root, self._list_env_files(root))
            is_active = active_name == name
            if is_active:
                await self._assert_no_running(project_id)

            self._write_atomic(path, content)
            backup = None
            if is_active:
                backup = self._backup_active_file(root)
                self._write_atomic(root / ".env", content)
            if remark is not None:
                await self._upsert_meta(project_id, name, remark, actor_id)

            _, warnings = parse_env_lines(content)
            return {
                "name": name,
                "is_active": is_active,
                "backup": backup,
                "warnings": warnings,
            }

    async def save_active_file(
        self, project_id: int, content: str, actor_id: int | None
    ) -> dict:
        """直接编辑当前生效的 .env（不经过环境快照）"""
        async with _project_lock(project_id):
            project = await self._get_project(project_id)
            root = self._resolve_root(project)
            await self._assert_no_running(project_id)
            self._ensure_envs_dir(root)
            backup = self._backup_active_file(root)
            self._write_atomic(root / ".env", content)
            _, warnings = parse_env_lines(content)
            return {"backup": backup, "warnings": warnings}

    async def create_env(
        self,
        project_id: int,
        name: str,
        source: str,
        content: str | None,
        remark: str | None,
        actor_id: int | None,
    ) -> dict:
        async with _project_lock(project_id):
            project = await self._get_project(project_id)
            root = self._resolve_root(project)
            path = self._safe_env_path(root, name)
            if path.exists():
                raise ConflictException(f"环境已存在: {name}")

            if source == "active":
                active_file = root / ".env"
                body = self._read_text(active_file) if active_file.is_file() else ""
            elif source == "empty":
                body = ""
            else:
                if content is None:
                    raise BadRequestException("source=content 时必须提供 content")
                body = content

            self._ensure_envs_dir(root)
            self._write_atomic(path, body)
            await self._upsert_meta(project_id, name, remark, actor_id)
            _, warnings = parse_env_lines(body)
            return {"name": name, "warnings": warnings}

    async def upload_env(
        self, project_id: int, filename: str, content: str, remark: str | None, actor_id: int | None
    ) -> dict:
        """把上传的文件落成环境快照，环境名由文件名推导"""
        stem = Path(filename or "").name.strip()
        if stem.lower().endswith(".env"):
            stem = stem[: -len(".env")]
        name = stem.strip()
        if not ENV_NAME_RE.fullmatch(name or ""):
            raise BadRequestException(
                "无法从文件名推导出合法环境名，请改用「新建环境」手动指定名称"
            )
        return await self.create_env(
            project_id, name, "content", content, remark, actor_id
        )

    async def apply_env(self, project_id: int, name: str) -> dict:
        """把环境快照覆盖写入 .env（切换生效环境）"""
        async with _project_lock(project_id):
            project = await self._get_project(project_id)
            root = self._resolve_root(project)
            path = self._safe_env_path(root, name)
            if not path.is_file():
                raise NotFoundException(f"环境不存在: {name}")
            await self._assert_no_running(project_id)
            content = self._read_text(path)
            backup = self._backup_active_file(root)
            self._write_atomic(root / ".env", content)
            return {"active_env": name, "backup": backup}

    async def rename_env(self, project_id: int, name: str, new_name: str) -> dict:
        async with _project_lock(project_id):
            project = await self._get_project(project_id)
            root = self._resolve_root(project)
            src = self._safe_env_path(root, name)
            dst = self._safe_env_path(root, new_name)
            if not src.is_file():
                raise NotFoundException(f"环境不存在: {name}")
            if dst.exists():
                raise ConflictException(f"环境已存在: {new_name}")
            try:
                src.rename(dst)
            except OSError as e:
                raise BadRequestException(f"环境重命名失败（{e}）")
            row = await self._get_meta(project_id, name)
            if row:
                row.name = new_name
                await self.db.commit()
            return {"name": new_name}

    async def export_env_file(self, project_id: int, name: str) -> str:
        """把环境内容导出为临时文件（供下载），返回临时文件路径"""
        data = await self.get_env(project_id, name)
        fd, tmp_name = tempfile.mkstemp(prefix=f"env_{name}_", suffix=".env")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(_to_lf(data["content"]))
        return tmp_name

    async def delete_env(self, project_id: int, name: str) -> None:
        async with _project_lock(project_id):
            project = await self._get_project(project_id)
            root = self._resolve_root(project)
            path = self._safe_env_path(root, name)
            if not path.is_file():
                raise NotFoundException(f"环境不存在: {name}")
            active_name, _ = self._detect_active(root, self._list_env_files(root))
            if active_name == name:
                raise BadRequestException("当前生效环境不允许删除，请先切换到其他环境")
            try:
                path.unlink()
            except OSError as e:
                raise BadRequestException(f"环境删除失败（{e}）")
            row = await self._get_meta(project_id, name)
            if row:
                await self.db.delete(row)
                await self.db.commit()
