"""项目自动化代码初始化服务

用户在新增项目时上传自动化代码压缩包，服务端完成：

1. 接口同步阶段（快，< 1s，失败即抛错且不留半成品）
   - 流式落盘 zip 到临时目录
   - zip 结构与安全检查 → 解析出唯一的顶层项目目录 <proj_dir>
   - 校验 <proj_dir>/tests 存在、目录未被其他项目占用
   - 置 code_init_status='pending' 后下发后台任务

2. 后台任务（慢，解压 + pip install 可能数分钟）
   - 解压 <proj_dir>/** 到临时 staging（目标目录此时完全未被触碰）
   - 复检 staging 内存在 tests 目录
   - 逐条投放到 {PROJECT_CODE_BASE_DIR}/<proj_dir>（同名覆盖、异名保留）
   - 回写 projects.auto_root_path = {BASE_DIR}/<proj_dir>/tests
   - 用项目的 python_path 执行 pip install -r requirements.txt
   - 写回 code_init_status / error / log / at

约定：
- 外部命令一律用 create_subprocess_exec 传参数组，不经过 shell，避免命令注入
- 后台任务使用独立短会话（AsyncSessionLocal），不长时间占用请求会话的连接
"""
import asyncio
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.project import Project
from app.utils.logger import logger

if TYPE_CHECKING:
    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession


# 进行中的状态：该状态下不允许再次上传，避免并发写同一目录
ACTIVE_STATUSES = {"pending", "extracting", "installing"}

# 日志上限（保留尾部，pip 报错在尾部）
_LOG_LIMIT = 100_000

# 顶层噪音条目（macOS/Windows 打包产物），不参与"唯一顶层目录"判定
_NOISE_TOP_LEVEL = {"__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}

# 项目目录名：允许字母、数字、点、下划线、短横线
_PROJ_DIR_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

# Windows 盘符前缀（如 C:）
_DRIVE_RE = re.compile(r"^[A-Za-z]:")

# 后台任务强引用，避免被 GC 回收
_running_tasks: set = set()

_CHUNK = 1024 * 1024


# ==================== 路径与参数校验 ====================


def base_dir() -> Path:
    """项目代码全局根目录（来自配置文件），已校验存在且可写"""
    raw = (settings.PROJECT_CODE_BASE_DIR or "").strip()
    if not raw:
        raise BadRequestException(
            "未配置项目代码全局根目录，请在服务端 .env 中配置 PROJECT_CODE_BASE_DIR"
        )
    path = Path(raw)
    _ensure_writable_dir(path, "项目代码全局根目录")
    return path.resolve()


def _ensure_writable_dir(path: Path, label: str) -> None:
    if not path.exists():
        raise BadRequestException(f"{label}不存在: {path}")
    if not path.is_dir():
        raise BadRequestException(f"{label}必须是目录: {path}")
    probe = path / f".write_test_{os.getpid()}.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception:
        raise BadRequestException(f"{label}无写入权限: {path}")


def validate_python_path(python_path: str | None) -> str:
    """校验项目 Python 解释器路径；支持绝对路径与 PATH 中的命令名（如 python）"""
    raw = (python_path or "").strip()
    if not raw:
        raise BadRequestException("请先为该项目配置 Python 解释器路径")

    looks_like_path = Path(raw).is_absolute() or os.sep in raw or (
        os.altsep is not None and os.altsep in raw
    )
    if looks_like_path:
        path = Path(raw)
        if not path.exists():
            raise BadRequestException(f"Python 解释器路径不存在: {raw}")
        if not path.is_file():
            raise BadRequestException(f"Python 解释器路径不是文件: {raw}")
        if not os.access(path, os.X_OK):
            raise BadRequestException(f"Python 解释器无执行权限: {raw}")
        return str(path)

    if shutil.which(raw) is None:
        raise BadRequestException(f"未找到可执行的 Python 解释器: {raw}")
    return raw


def tmp_root() -> Path:
    """上传临时文件根目录"""
    raw = (settings.PROJECT_CODE_TMP_DIR or "").strip()
    root = Path(raw) if raw else Path(tempfile.gettempdir())
    root = root / "project_code_init"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_within(root: Path, target: Path) -> bool:
    """校验 target 是否落在 root 内（防 ../ 越界）"""
    try:
        return target.resolve().is_relative_to(root.resolve())
    except (ValueError, OSError):
        return False


# ==================== 压缩包解析与校验 ====================


def _split_zip_name(name: str) -> list[str]:
    """zip 条目名拆段：兼容 \\ 分隔符，过滤空段与 '.'（保留 '..' 供越界检查）"""
    return [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]


def _validate_entry_name(name: str) -> list[str]:
    """校验单个条目路径合法性，返回拆好的路径段"""
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE_RE.match(normalized):
        raise BadRequestException(f"压缩包内存在非法路径: {name}")
    parts = _split_zip_name(normalized)
    if any(p == ".." for p in parts):
        raise BadRequestException(f"压缩包内存在非法路径: {name}")
    return parts


def inspect_zip(zip_path: Path) -> str:
    """打开 zip 做结构与安全校验，返回唯一的顶层项目目录名 <proj_dir>"""
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise BadRequestException("压缩包已损坏或不是合法的 zip 文件")
    except Exception as e:
        raise BadRequestException(f"压缩包无法读取: {e}")

    with zf:
        infos = zf.infolist()
        if not infos:
            raise BadRequestException("压缩包内容为空")

        if len(infos) > settings.PROJECT_CODE_MAX_FILES:
            raise BadRequestException(
                f"压缩包文件数（{len(infos)}）超过上限 {settings.PROJECT_CODE_MAX_FILES}"
            )

        total_size = sum(i.file_size for i in infos)
        max_bytes = settings.PROJECT_CODE_MAX_UNCOMPRESSED_MB * 1024 * 1024
        if total_size > max_bytes:
            raise BadRequestException(
                f"压缩包解压后体积（{total_size // (1024 * 1024)}MB）超过上限 "
                f"{settings.PROJECT_CODE_MAX_UNCOMPRESSED_MB}MB"
            )

        seen: set[str] = set()
        top_dirs: list[str] = []
        top_files: list[str] = []
        for info in infos:
            parts = _validate_entry_name(info.filename)
            if not parts:
                continue
            if stat.S_ISLNK(info.external_attr >> 16):
                raise BadRequestException(f"压缩包内存在符号链接，已拒绝: {info.filename}")

            key = "/".join(parts)
            if key in seen:
                raise BadRequestException(f"压缩包内存在重名条目: {info.filename}")
            seen.add(key)

            top = parts[0]
            if top in _NOISE_TOP_LEVEL:
                continue
            if len(parts) == 1 and not info.is_dir():
                # 顶层散落的文件：不透出，也不会被投放（仅记录）
                if top not in top_files:
                    top_files.append(top)
            elif top not in top_dirs:
                top_dirs.append(top)

        if not top_dirs:
            raise BadRequestException(
                "压缩包内未找到项目文件夹，请把整个项目文件夹（内含 tests 目录）打包后上传"
            )
        if len(top_dirs) > 1:
            raise BadRequestException(
                f"压缩包顶层存在多个文件夹（{'、'.join(top_dirs[:5])}），请只打包一个项目文件夹"
            )

        proj_dir = top_dirs[0]
        if not _PROJ_DIR_RE.fullmatch(proj_dir):
            raise BadRequestException(f"项目文件夹名称不合法: {proj_dir}")

        # 顶层直接是 tests/ 的情况：明显是把文件夹内容而非文件夹本身打了包
        if proj_dir.lower() == "tests":
            raise BadRequestException(
                "压缩包内未找到项目文件夹，请把整个项目文件夹（内含 tests 目录）打包后上传"
            )

        has_tests = any(
            len(p) >= 2 and p[0] == proj_dir and p[1] == "tests"
            for p in (_split_zip_name(i.filename) for i in infos)
        )
        if not has_tests:
            raise BadRequestException(f"项目文件夹 {proj_dir} 内未找到 tests 目录")

        if top_files:
            logger.info(f"[项目代码初始化] 已忽略压缩包顶层散落文件: {top_files}")

        return proj_dir


async def save_upload(upload: "UploadFile") -> Path:
    """分块流式落盘上传文件（不整包读内存），返回临时 zip 路径"""
    filename = (upload.filename or "").strip()
    if not filename.lower().endswith(".zip"):
        raise BadRequestException("请上传 .zip 格式的压缩包")

    max_bytes = settings.PROJECT_CODE_UPLOAD_MAX_MB * 1024 * 1024
    dest = tmp_root() / f"{uuid.uuid4().hex}.zip"
    total = 0
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = await upload.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise BadRequestException(
                        f"压缩包超过大小上限 {settings.PROJECT_CODE_UPLOAD_MAX_MB}MB"
                    )
                f.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    if total == 0:
        dest.unlink(missing_ok=True)
        raise BadRequestException("上传的压缩包为空")
    return dest


# ==================== 解压与投放 ====================


def extract_to_staging(zip_path: Path, staging: Path, proj_dir: str) -> tuple[int, int]:
    """仅解压 <proj_dir>/** 到 staging/<proj_dir>/**，返回 (文件数, 字节数)"""
    staging_proj = staging / proj_dir
    staging_proj.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.PROJECT_CODE_MAX_UNCOMPRESSED_MB * 1024 * 1024
    total = 0
    count = 0

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            parts = _split_zip_name(info.filename)
            if not parts or parts[0] != proj_dir:
                continue
            rel = parts[1:]
            if not rel:
                continue  # 项目目录自身

            target = staging_proj.joinpath(*rel)
            if not _is_within(staging_proj, target):
                raise BadRequestException(f"压缩包内存在越界路径: {info.filename}")

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                while True:
                    chunk = src.read(_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise BadRequestException(
                            f"解压后体积超过上限 {settings.PROJECT_CODE_MAX_UNCOMPRESSED_MB}MB"
                        )
                    dst.write(chunk)
            count += 1
    return count, total


def deploy(staging_proj: Path, target: Path) -> int:
    """把 staging/<proj_dir> 逐条投放到目标目录：同名覆盖、异名保留；返回文件数"""
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in staging_proj.rglob("*"):
        if src.is_symlink():
            continue
        rel = src.relative_to(staging_proj)
        dst = target / rel
        if not _is_within(target, dst):
            raise BadRequestException(f"投放路径越界: {rel}")
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copied += 1
    return copied


def find_requirements(project_root: Path) -> Path | None:
    """项目根下的 requirements.txt；再回退 tests/ 下"""
    for candidate in (
        project_root / "requirements.txt",
        project_root / "tests" / "requirements.txt",
    ):
        if candidate.is_file():
            return candidate
    return None


# ==================== 依赖安装 ====================


def _decode(raw: bytes | None) -> str:
    if not raw:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


async def run_pip_install(
    python_path: str, requirements: Path, cwd: Path
) -> tuple[int, str]:
    """用指定解释器执行 pip install -r，返回 (退出码, 输出)；超时则杀进程"""
    cmd = [
        python_path, "-m", "pip", "install",
        "-r", str(requirements),
        "--disable-pip-version-check",
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        return 1, f"Python 解释器路径不存在: {python_path}"
    except Exception as e:
        return 1, f"启动 pip 失败: {e}"

    try:
        raw, _ = await asyncio.wait_for(
            proc.communicate(), timeout=settings.PROJECT_CODE_INIT_TIMEOUT
        )
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass
        return 1, f"pip install 超时（超过 {settings.PROJECT_CODE_INIT_TIMEOUT} 秒），已终止"

    return proc.returncode or 0, _strip_ansi(_decode(raw))


# ==================== 状态与日志读写（独立短会话） ====================


def _truncate_log(text: str) -> str:
    if len(text) <= _LOG_LIMIT:
        return text
    return "...（前部已截断）\n" + text[-_LOG_LIMIT:]


def _brief(text: str, limit: int = 500) -> str:
    """单行摘要，供列表 tooltip 展示"""
    s = " ".join((text or "").split())
    return s if len(s) <= limit else s[:limit] + "..."


def _tail_summary(text: str, limit: int = 500) -> str:
    """取输出尾部的最后几行作为失败摘要（pip 报错在尾部）"""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return _brief(" | ".join(lines[-5:]), limit)


async def _update_project(project_id: int, **values) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(Project).where(Project.id == project_id).values(**values))
        await db.commit()


async def _finish(project_id: int, status: str, logs: list[str], error: str | None = None) -> None:
    await _update_project(
        project_id,
        code_init_status=status,
        code_init_error=error,
        code_init_log=_truncate_log("\n".join(logs)),
        code_init_at=datetime.now(),
    )


async def _load_pip_context(project_id: int) -> tuple[Path, str]:
    """读取 pip 执行所需的项目根目录与解释器路径"""
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(Project.auto_root_path, Project.python_path).where(Project.id == project_id)
            )
        ).first()
    if not row or not row[0]:
        raise BadRequestException("该项目尚未生成自动化根路径，请先上传代码包")
    return Path(row[0]).parent, (row[1] or "").strip()


async def _execute_pip(project_id: int, logs: list[str]) -> None:
    """查找 requirements.txt 并用项目解释器安装；无则直接置 ready"""
    project_root, python_path = await _load_pip_context(project_id)
    requirements = find_requirements(project_root)
    if requirements is None:
        logs.append("[依赖] 未找到 requirements.txt，跳过依赖安装")
        await _finish(project_id, "ready", logs)
        return

    validate_python_path(python_path)
    await _update_project(
        project_id,
        code_init_status="installing",
        code_init_log=_truncate_log("\n".join(logs)),
    )

    logs.append(f"[依赖] 解释器: {python_path}")
    logs.append(f"[依赖] pip install -r {requirements}")
    code, output = await run_pip_install(python_path, requirements, project_root)
    if output:
        logs.append(output)
    logs.append(f"[依赖] 退出码: {code}")

    if code != 0:
        await _finish(
            project_id, "failed", logs,
            error=_tail_summary(output) or f"pip install 失败（退出码 {code}）",
        )
    else:
        await _finish(project_id, "ready", logs)


# ==================== 后台任务 ====================


async def _run_code_init(project_id: int, proj_dir: str, zip_path_str: str) -> None:
    """后台任务：解压 → 投放 → 回写根路径 → 安装依赖"""
    zip_path = Path(zip_path_str)
    logs = [f"[受理] 项目代码包初始化开始，项目目录: {proj_dir}"]
    staging: Path | None = None
    try:
        target = base_dir() / proj_dir

        staging = Path(
            tempfile.mkdtemp(prefix=f"projinit_{project_id}_", dir=str(tmp_root()))
        )
        files, size = await asyncio.to_thread(extract_to_staging, zip_path, staging, proj_dir)
        logs.append(f"[解压] {files} 个文件，共 {size} 字节")

        staging_proj = staging / proj_dir
        if not (staging_proj / "tests").is_dir():
            raise BadRequestException(f"解压后未找到 {proj_dir}/tests 目录")

        copied = await asyncio.to_thread(deploy, staging_proj, target)
        logs.append(f"[投放] {copied} 个文件 -> {target}")

        auto_root = str(target / "tests")
        await _update_project(project_id, auto_root_path=auto_root)
        logs.append(f"[路径] 自动化根路径 = {auto_root}")

        await _execute_pip(project_id, logs)
    except Exception as e:
        logger.exception(f"[项目代码初始化] 执行失败 project_id={project_id}")
        logs.append(f"[失败] {e}")
        await _finish(project_id, "failed", logs, error=_brief(str(e) or e.__class__.__name__))
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        zip_path.unlink(missing_ok=True)


async def _run_pip_only(project_id: int) -> None:
    """后台任务：仅重跑依赖安装（代码已投放）"""
    logs = ["[重试] 重新安装项目依赖"]
    try:
        await _execute_pip(project_id, logs)
    except Exception as e:
        logger.exception(f"[项目代码初始化] 重装依赖失败 project_id={project_id}")
        logs.append(f"[失败] {e}")
        await _finish(project_id, "failed", logs, error=_brief(str(e) or e.__class__.__name__))


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


def dispatch_project_code_init(project_id: int, proj_dir: str, zip_path: str) -> None:
    """下发代码初始化任务（调用方需已 commit 状态为 pending）"""
    _spawn(_run_code_init(project_id, proj_dir, zip_path))


def dispatch_project_code_install(project_id: int) -> None:
    """下发"仅重装依赖"任务（调用方需已 commit 状态为 installing）"""
    _spawn(_run_pip_only(project_id))


# ==================== 接口层服务 ====================


class ProjectInitService:
    """供 API 层调用的同步阶段逻辑"""

    def __init__(self, db: "AsyncSession"):
        self.db = db

    async def _get_project(self, project_id: int) -> Project:
        project = (
            await self.db.execute(select(Project).where(Project.id == project_id))
        ).scalar_one_or_none()
        if not project:
            raise NotFoundException("项目不存在")
        return project

    async def _ensure_dir_available(self, project_id: int, directory: Path) -> None:
        """确保目标目录未被其他项目占用（其他项目的 auto_root_path 落在该目录内）"""
        target = directory.resolve()
        rows = (
            await self.db.execute(
                select(Project.id, Project.name, Project.auto_root_path).where(
                    Project.id != project_id,
                    Project.auto_root_path.is_not(None),
                )
            )
        ).all()
        for _pid, name, path in rows:
            if not path:
                continue
            try:
                existing = Path(path).resolve()
            except OSError:
                continue
            if existing == target or existing.is_relative_to(target):
                raise ConflictException(
                    f"目录 {target} 已被项目「{name}」使用，"
                    "请更换项目文件夹名称或先清理该目录"
                )

    async def upload_and_dispatch(
        self, project_id: int, upload: "UploadFile", user_id: int
    ) -> dict:
        """上传代码包并触发初始化（同步阶段）"""
        project = await self._get_project(project_id)
        if project.code_init_status in ACTIVE_STATUSES:
            raise ConflictException("该项目代码正在初始化中，请稍后再试")

        root = base_dir()
        validate_python_path(project.python_path)

        zip_path = await save_upload(upload)
        try:
            proj_dir = inspect_zip(zip_path)
            await self._ensure_dir_available(project_id, root / proj_dir)
        except Exception:
            zip_path.unlink(missing_ok=True)
            raise

        project.code_init_status = "pending"
        project.code_init_error = None
        project.code_init_log = f"已受理，等待后台任务执行…（项目目录: {proj_dir}）"
        project.code_init_by = user_id
        await self.db.commit()

        dispatch_project_code_init(project_id, proj_dir, str(zip_path))
        logger.info(f"[项目代码初始化] 已下发 project_id={project_id} proj_dir={proj_dir}")
        return {
            "project_id": project_id,
            "project_dir": proj_dir,
            "code_init_status": "pending",
        }

    async def reinstall_and_dispatch(self, project_id: int) -> dict:
        """仅重跑依赖安装（免重新上传代码包）"""
        project = await self._get_project(project_id)
        if project.code_init_status != "failed":
            raise BadRequestException("仅初始化失败的项目可以重装依赖")

        _, python_path = await _load_pip_context(project_id)
        validate_python_path(python_path)
        project_root = Path(project.auto_root_path).parent
        if find_requirements(project_root) is None:
            raise BadRequestException(
                f"项目目录 {project_root} 下未找到 requirements.txt，请重新上传代码包"
            )

        project.code_init_status = "installing"
        project.code_init_error = None
        await self.db.commit()

        dispatch_project_code_install(project_id)
        return {"project_id": project_id, "code_init_status": "installing"}
