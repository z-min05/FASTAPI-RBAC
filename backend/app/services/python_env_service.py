"""Python 虚拟环境管理服务（Miniconda）

设计要点（详见 docs/Python环境管理模块设计.md）：

- 环境一律用 `conda create -p <env_path> python=<version>`（prefix 模式）创建，
  路径由 ``settings.CONDA_ENV_ROOT + name`` 推导；这样路径完全由配置文件决定，
  也不污染 Miniconda 自带的 envs 目录。
- conda 命令慢，因此所有动作异步：接口先把记录置为 pending/creating/syncing/deleting
  并立即返回，由使用者刷新查看结果。
- 一致性策略：真实环境在文件系统、记录在 PostgreSQL，跨系统无法真正原子提交，
  故删除采用「先删真实环境、成功后删数据库记录」的固定顺序 + 状态回滚，把不一致
  窗口收敛为"记录在、环境已删"这一种可由同步校验发现的情形，绝不出现
  "记录显示 ready 但环境已不存在"的静默错误。
- 后台任务自建 ``AsyncSessionLocal``，不复用请求会话；状态流转用**条件更新认领**，
  多 worker 部署下不会重复执行。
"""
import asyncio
import os
import re
import subprocess
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.pagination import PaginationParams
from app.db.session import AsyncSessionLocal
from app.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.python_env import PythonEnv
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.python_env import PythonEnvCreate, PythonEnvUpdate
from app.utils.logger import logger

# 环境名规范：只允许字母/数字/下划线/中划线，避免拼接出路径
_ENV_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
# 进行中状态：接口据此拒绝并发操作，前端据此决定是否轮询
ACTIVE_STATUSES = {"pending", "creating", "syncing", "deleting"}
# conda 输出入库上限（字符）
_OUTPUT_LIMIT = 2000
# 后台任务强引用，避免被 GC 回收
_running_tasks: set = set()


def _strip_ansi(text: str) -> str:
    """去掉 ANSI 颜色控制字符"""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# ---------- 配置与路径 ----------

def require_conda_ready() -> str:
    """校验 conda 可用，返回 conda 可执行文件路径"""
    conda_exe = settings.conda_exe
    if not conda_exe:
        raise BadRequestException("未配置 conda，请在配置文件中填写 CONDA_HOME 或 CONDA_EXE")
    if not os.path.exists(conda_exe):
        raise BadRequestException(
            f"conda 可执行文件不存在: {conda_exe}，请检查 CONDA_HOME / CONDA_EXE 配置"
        )
    return conda_exe


def _env_root() -> str:
    root = (settings.CONDA_ENV_ROOT or "").strip()
    if not root:
        raise BadRequestException("未配置虚拟环境根目录 CONDA_ENV_ROOT")
    return root


def resolve_paths(name: str) -> tuple[str, str]:
    """由环境名推导 (env_path, python_path)，根目录来自配置文件

    统一 normpath：把配置里可能出现的 `/` 与结尾分隔符归一为平台原生分隔符，
    保证入库路径与磁盘实际路径、唯一性判据三者一致。
    """
    env_path = os.path.normpath(os.path.join(_env_root(), name))
    if os.name == "nt":
        python_path = os.path.join(env_path, "python.exe")
    else:
        python_path = os.path.join(env_path, "bin", "python")
    return env_path, python_path


# ---------- conda 命令执行 ----------

async def _run_conda(args: list[str], timeout: int) -> tuple[int, str]:
    """执行 conda 命令，返回 (returncode, 去色截断后的输出)

    超时或启动失败时 returncode 返回 -1（输出中带原因），调用方据此判失败。
    """
    conda_exe = settings.conda_exe or ""
    try:
        proc = await asyncio.create_subprocess_exec(
            conda_exe, *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        return -1, f"conda 可执行文件不存在: {conda_exe}"
    except Exception as e:  # noqa: BLE001 - 启动失败一律按命令失败处理
        return -1, f"启动 conda 失败: {e}"

    try:
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5)
        except Exception:  # noqa: BLE001 - 回收进程输出失败不影响判定
            pass
        return -1, f"conda 命令执行超时（>{timeout} 秒），已强制终止"

    code = proc.returncode if proc.returncode is not None else -1
    text = _strip_ansi(raw.decode("utf-8", errors="replace"))
    if len(text) > _OUTPUT_LIMIT:
        text = "[输出过长，仅保留尾部]\n" + text[-_OUTPUT_LIMIT:]
    return code, text


# ---------- 响应组装 ----------

def to_response(env: PythonEnv, created_by_name: str | None = None) -> dict:
    return {
        "id": env.id,
        "name": env.name,
        "python_version": env.python_version,
        "env_path": env.env_path,
        "python_path": env.python_path,
        "status": env.status,
        "error_msg": env.error_msg,
        "last_output": env.last_output,
        "last_synced_at": env.last_synced_at,
        "description": env.description,
        "created_by": env.created_by,
        "created_by_name": created_by_name,
        "created_at": env.created_at,
        "updated_at": env.updated_at,
    }


class PythonEnvService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BaseRepository(PythonEnv, db)

    # ---------- 查询 ----------

    async def paginate(
        self,
        params: PaginationParams,
        keyword: str | None = None,
        status: str | None = None,
    ):
        filters = []
        if keyword:
            filters.append(PythonEnv.name.ilike(f"%{keyword}%"))
        if status:
            filters.append(PythonEnv.status == status)
        return await self.repo.get_paginated(
            params, filters=filters, order_by=[PythonEnv.id.desc()]
        )

    async def get(self, env_id: int) -> PythonEnv:
        env = await self.db.get(PythonEnv, env_id)
        if not env:
            raise NotFoundException("Python 环境不存在")
        return env

    async def user_name_map(self, user_ids: set[int | None]) -> dict[int, str]:
        """创建人 id → 展示名（昵称优先，回退用户名）"""
        ids = [i for i in user_ids if i]
        if not ids:
            return {}
        stmt = select(User.id, User.nickname, User.username).where(User.id.in_(ids))
        rows = (await self.db.execute(stmt)).all()
        return {r[0]: (r[1] or r[2] or f"#{r[0]}") for r in rows}

    async def list_options(self) -> list[dict]:
        """仅返回 ready 环境，供项目管理选择解释器"""
        stmt = (
            select(PythonEnv)
            .where(PythonEnv.status == "ready")
            .order_by(PythonEnv.name.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "python_version": r.python_version,
                "python_path": r.python_path,
            }
            for r in rows
        ]

    # ---------- 增 ----------

    async def create(self, data: PythonEnvCreate, user_id: int | None) -> PythonEnv:
        """建记录（pending）并提交；后台任务由接口层在提交后下发"""
        require_conda_ready()
        name = data.name.strip()
        # schema 已做 pattern 校验，这里再兜一层（含 strip 后为空的情况）
        if not _ENV_NAME_RE.match(name):
            raise BadRequestException("环境名仅允许字母、数字、下划线、中划线，长度 1-50")

        versions = settings.conda_python_versions
        if data.python_version not in versions:
            raise BadRequestException(
                f"不支持的 Python 版本: {data.python_version}，可选: {', '.join(versions)}"
            )

        env_path, python_path = resolve_paths(name)

        exists = (await self.db.execute(
            select(PythonEnv.id)
            .where((PythonEnv.name == name) | (PythonEnv.env_path == env_path))
            .limit(1)
        )).scalar()
        if exists is not None:
            raise ConflictException(f"环境 {name} 已存在（同名或同路径），请更换名称")

        # 磁盘上已有同名目录：直接创建会被 conda 覆盖，先拦下
        if os.path.exists(env_path):
            raise ConflictException(f"目录已存在: {env_path}，请更换环境名或先清理该目录")

        env = PythonEnv(
            name=name,
            python_version=data.python_version,
            env_path=env_path,
            python_path=python_path,
            status="pending",
            description=data.description,
            created_by=user_id,
        )
        self.db.add(env)
        await self.db.flush()
        # 必须先提交，后台任务用的是另一个会话，否则读不到这条记录
        await self.db.commit()
        await self.db.refresh(env)
        return env

    # ---------- 改 ----------

    async def update(self, env_id: int, data: PythonEnvUpdate) -> PythonEnv:
        """仅允许修改备注；name / python_version 创建后不可变"""
        env = await self.get(env_id)
        if env.status in ACTIVE_STATUSES:
            raise ConflictException(f"当前状态（{env.status}）不可编辑，请稍后再试")
        # 用 exclude_unset 区分"未传该字段"与"显式传 null（清空备注）"
        fields = data.model_dump(exclude_unset=True)
        if "description" in fields:
            env.description = fields["description"]
        await self.db.flush()
        await self.db.refresh(env)
        return env

    # ---------- 删 ----------

    async def request_delete(self, env_id: int) -> tuple[PythonEnv, str]:
        """置为 deleting 并提交，返回 (记录, 删除前状态) 供后台任务回滚使用"""
        env = await self.get(env_id)
        if env.status in ACTIVE_STATUSES:
            raise ConflictException(f"当前状态（{env.status}）不可删除，请稍后再试")
        prev_status = env.status
        env.status = "deleting"
        env.error_msg = None
        await self.db.commit()
        await self.db.refresh(env)
        return env, prev_status

    # ---------- 同步校验 ----------

    async def request_sync(self, env_ids: list[int] | None) -> list[tuple[int, str]]:
        """把待同步环境置为 syncing 并提交，返回 [(id, 原状态)] 供后台任务使用"""
        stmt = select(PythonEnv)
        if env_ids:
            stmt = stmt.where(PythonEnv.id.in_(env_ids))
        else:
            stmt = stmt.where(PythonEnv.status.notin_(ACTIVE_STATUSES))

        rows = list((await self.db.execute(stmt)).scalars().all())
        if not rows:
            if env_ids:
                raise NotFoundException(f"环境不存在: {env_ids}")
            return []

        targets = [(r.id, r.status) for r in rows if r.status not in ACTIVE_STATUSES]
        if env_ids and not targets:
            raise ConflictException("当前状态不可同步，请稍后再试")

        for env in rows:
            if env.status in ACTIVE_STATUSES:
                continue
            env.status = "syncing"
            env.error_msg = None
        await self.db.commit()
        return targets


# ---------- 后台任务 ----------

async def _claim(env_id: int, from_status: str, to_status: str) -> bool:
    """状态条件更新认领：影响行数为 0 说明已被其他任务处理（多 worker 安全）"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(PythonEnv)
            .where(PythonEnv.id == env_id, PythonEnv.status == from_status)
            .values(status=to_status)
        )
        await db.commit()
        return (result.rowcount or 0) > 0


async def _mark_failed(env_id: int, message: str) -> None:
    """兜底：把进行中的记录置为 failed（独立会话）"""
    try:
        async with AsyncSessionLocal() as db:
            env = await db.get(PythonEnv, env_id)
            if env and env.status in {"pending", "creating", "syncing"}:
                env.status = "failed"
                env.error_msg = message
                await db.commit()
    except Exception as e:  # noqa: BLE001 - 兜底逻辑自身异常仅记日志
        logger.error(f"标记 Python 环境 {env_id} 失败状态时出错: {e}")


async def _restore_status(env_id: int, prev_status: str, message: str) -> None:
    """删除失败/异常时把状态回滚到删除前，避免记录卡在 deleting"""
    try:
        async with AsyncSessionLocal() as db:
            env = await db.get(PythonEnv, env_id)
            if env and env.status == "deleting":
                env.status = prev_status
                env.error_msg = message
                await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.error(f"回滚 Python 环境 {env_id} 状态时出错: {e}")


async def _create_env_task(env_id: int) -> None:
    """后台任务：执行 conda create"""
    try:
        if not await _claim(env_id, "pending", "creating"):
            logger.info(f"Python 环境 {env_id} 创建任务未认领（状态已变更），跳过")
            return

        # conda 命令可能跑数分钟，先用一个短会话把参数读出来并释放连接，
        # 避免长时间 idle-in-transaction 占用连接池
        async with AsyncSessionLocal() as db:
            env = await db.get(PythonEnv, env_id)
            if not env:
                logger.warning(f"Python 环境 {env_id} 记录已不存在，创建任务终止")
                return
            name, env_path, version = env.name, env.env_path, env.python_version

        logger.info(f"Python 环境创建开始 env={name} path={env_path} python={version}")
        code, output = await _run_conda(
            ["create", "-y", "-p", env_path, f"python={version}"],
            settings.CONDA_CMD_TIMEOUT,
        )

        async with AsyncSessionLocal() as db:
            env = await db.get(PythonEnv, env_id)
            if not env:
                logger.warning(f"Python 环境 {env_id} 记录已不存在，创建结果未写回")
                return
            if code != 0:
                env.status = "failed"
                env.error_msg = f"conda create 失败（退出码 {code}）"
                env.last_output = output
                await db.commit()
                logger.warning(f"Python 环境创建失败 env={name} code={code}\n{output}")
                return
            env.status = "ready"
            env.error_msg = None
            env.last_output = output
            env.last_synced_at = datetime.now()
            await db.commit()
            logger.info(f"Python 环境创建完成 env={name} path={env_path}")
    except Exception as e:  # noqa: BLE001 - 后台任务不得抛出到事件循环
        logger.exception(f"Python 环境创建任务异常 env_id={env_id}: {e}")
        await _mark_failed(env_id, f"创建任务异常: {e}")


async def _delete_env_task(env_id: int, prev_status: str) -> None:
    """后台任务：先删真实环境，成功后删数据库记录；失败回滚状态"""
    try:
        async with AsyncSessionLocal() as db:
            env = await db.get(PythonEnv, env_id)
            if not env:
                logger.info(f"Python 环境 {env_id} 记录已不存在，删除任务终止")
                return
            name, env_path = env.name, env.env_path

        logger.info(f"Python 环境删除开始 env={name} path={env_path}")
        code, output = await _run_conda(
            ["env", "remove", "-y", "-p", env_path],
            settings.CONDA_CMD_TIMEOUT,
        )

        # 环境本就不存在（如已被手工删除）视为删除成功，保证幂等
        lowered = output.lower()
        already_gone = "does not exist" in lowered or "not found" in lowered
        if code != 0 and not already_gone:
            async with AsyncSessionLocal() as db:
                env = await db.get(PythonEnv, env_id)
                if env and env.status == "deleting":
                    env.status = prev_status
                    env.error_msg = f"conda env remove 失败（退出码 {code}）"
                    env.last_output = output
                    await db.commit()
            logger.warning(f"Python 环境删除失败 env={name} code={code}\n{output}")
            return

        # 真实环境已删除 → 再删数据库记录（同一事务）
        try:
            async with AsyncSessionLocal() as db:
                env = await db.get(PythonEnv, env_id)
                if not env:
                    logger.info(f"Python 环境 {env_id} 记录已不存在，无需删除")
                    return
                await db.delete(env)
                await db.commit()
            logger.info(f"Python 环境删除完成 env={name} path={env_path}")
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Python 环境 {env_id} 记录删除失败: {e}")
            await _restore_status(env_id, prev_status, f"环境已删除但记录删除失败: {e}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Python 环境删除任务异常 env_id={env_id}: {e}")
        await _restore_status(env_id, prev_status, f"删除任务异常: {e}")


async def _sync_env_task(targets: list[tuple[int, str]]) -> None:
    """后台任务：以文件系统为主判据核对环境真实状态"""
    ids = [t[0] for t in targets]
    try:
        async with AsyncSessionLocal() as db:
            for env_id, prev_status in targets:
                env = await db.get(PythonEnv, env_id)
                if not env or env.status != "syncing":
                    continue
                if os.path.isdir(env.env_path) and os.path.isfile(env.python_path):
                    env.status = "ready"
                    env.error_msg = None
                elif prev_status == "failed":
                    # 原本就是创建失败，保留失败态与原因，不升级为 lost
                    env.status = "failed"
                    env.error_msg = "创建未成功，环境目录或解释器不存在"
                else:
                    env.status = "lost"
                    env.error_msg = "环境目录或解释器不存在，可能已被手工删除"
                env.last_synced_at = datetime.now()
            await db.commit()
            logger.info(f"Python 环境同步完成 count={len(targets)}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Python 环境同步任务异常 ids={ids}: {e}")
        try:
            async with AsyncSessionLocal() as db:
                for env_id, prev_status in targets:
                    env = await db.get(PythonEnv, env_id)
                    if env and env.status == "syncing":
                        env.status = prev_status
                        env.error_msg = f"同步任务异常: {e}"
                await db.commit()
        except Exception as e2:  # noqa: BLE001
            logger.error(f"回滚 Python 环境同步状态时出错: {e2}")


def _spawn(coro) -> None:
    """下发后台任务并保持强引用，避免被 GC 回收"""
    task = asyncio.create_task(coro)
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


def dispatch_env_create(env_id: int) -> None:
    """下发异步创建任务（调用前必须已提交记录）"""
    _spawn(_create_env_task(env_id))


def dispatch_env_delete(env_id: int, prev_status: str) -> None:
    """下发异步删除任务"""
    _spawn(_delete_env_task(env_id, prev_status))


def dispatch_env_sync(targets: list[tuple[int, str]]) -> None:
    """下发异步同步校验任务"""
    _spawn(_sync_env_task(targets))
