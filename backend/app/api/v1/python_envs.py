"""Python 环境管理（Miniconda）路由

- 所有涉及 conda 的动作（创建/删除/同步）均为**异步**：接口只把记录置为
  pending/deleting/syncing 并立即返回，由前端刷新或轮询查看最终结果。
- 权限走 RBAC 细粒度授权（python-env:list/create/update/delete/sync）。
- `CONDA_ENABLED=false` 时 CRUD/同步接口返回 403（与 Agent 的 require_agent_enabled 同思路）；
  仅 `/options` 不挂开关，因为项目管理页会无条件调用它做联动。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.pagination import PaginationParams
from app.core.response import Response
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.exceptions import ForbiddenException
from app.models.user import User
from app.schemas.python_env import PythonEnvCreate, PythonEnvUpdate
from app.services.python_env_service import (
    PythonEnvService,
    dispatch_env_create,
    dispatch_env_delete,
    dispatch_env_sync,
    to_response,
)

router = APIRouter(prefix="/python-envs", tags=["Python 环境管理"])


async def require_conda_enabled():
    """Python 环境管理总开关（未启用时返回 403）"""
    if not settings.CONDA_ENABLED:
        raise ForbiddenException("Python 环境管理未启用")
    return True


# ==================== 仅供登录（无细粒度权限） ====================


@router.get("/options", summary="Python 环境下拉选项（仅登录，供项目管理选择解释器）")
async def list_env_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # 不加 CONDA_ENABLED 开关：供项目管理联动读取，未启用/无可用环境时返回空列表即可，
    # 避免项目管理页面因 403 弹出无意义的错误提示
    service = PythonEnvService(db)
    data = await service.list_options()
    return Response.success(data=data)


@router.get("/versions", summary="可选的 Python 版本列表（配置文件静态列表）")
async def list_python_versions(
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(get_current_active_user),
):
    return Response.success(data={"versions": settings.conda_python_versions})


# ==================== 增删查改（RBAC） ====================


@router.get("", summary="Python 环境列表")
async def list_envs(
    params: PaginationParams = Depends(),
    keyword: str | None = Query(None, description="关键字（环境名）"),
    status: str | None = Query(None, description="状态过滤"),
    db: AsyncSession = Depends(get_db),
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(require_permissions("python-env:list")),
):
    service = PythonEnvService(db)
    result = await service.paginate(params, keyword, status)
    name_map = await service.user_name_map({r.created_by for r in result.items})
    items = [to_response(r, name_map.get(r.created_by)) for r in result.items]
    return Response.success(data={
        "items": items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    })


@router.post("", summary="新增 Python 环境（异步创建）")
async def create_env(
    data: PythonEnvCreate,
    db: AsyncSession = Depends(get_db),
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(require_permissions("python-env:create")),
):
    service = PythonEnvService(db)
    env = await service.create(data, current_user.id)
    # 记录已提交，此时再下发后台任务，保证任务能读到该行
    dispatch_env_create(env.id)
    return Response.success(
        data=to_response(env, current_user.nickname or current_user.username),
        message="创建任务已提交，请稍后刷新查看结果",
    )


@router.post("/sync-all", summary="全量同步校验环境真实状态（异步）")
async def sync_all_envs(
    db: AsyncSession = Depends(get_db),
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(require_permissions("python-env:sync")),
):
    service = PythonEnvService(db)
    targets = await service.request_sync(None)
    if targets:
        dispatch_env_sync(targets)
    return Response.success(
        data={"count": len(targets), "status": "syncing"},
        message="同步任务已提交，请稍后刷新查看结果",
    )


@router.get("/{env_id}", summary="Python 环境详情")
async def get_env(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(require_permissions("python-env:list")),
):
    service = PythonEnvService(db)
    env = await service.get(env_id)
    name_map = await service.user_name_map({env.created_by})
    return Response.success(data=to_response(env, name_map.get(env.created_by)))


@router.put("/{env_id}", summary="编辑 Python 环境（仅备注）")
async def update_env(
    env_id: int,
    data: PythonEnvUpdate,
    db: AsyncSession = Depends(get_db),
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(require_permissions("python-env:update")),
):
    service = PythonEnvService(db)
    env = await service.update(env_id, data)
    name_map = await service.user_name_map({env.created_by})
    return Response.success(data=to_response(env, name_map.get(env.created_by)), message="保存成功")


@router.delete("/{env_id}", summary="删除 Python 环境（异步，环境与记录一并删除）")
async def delete_env(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(require_permissions("python-env:delete")),
):
    service = PythonEnvService(db)
    _, prev_status = await service.request_delete(env_id)
    dispatch_env_delete(env_id, prev_status)
    return Response.success(
        data={"id": env_id, "status": "deleting"},
        message="删除任务已提交，请稍后刷新查看结果",
    )


@router.post("/{env_id}/sync", summary="同步校验单个环境真实状态（异步）")
async def sync_env(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _enabled: bool = Depends(require_conda_enabled),
    current_user: User = Depends(require_permissions("python-env:sync")),
):
    service = PythonEnvService(db)
    targets = await service.request_sync([env_id])
    dispatch_env_sync(targets)
    return Response.success(
        data={"id": env_id, "status": "syncing"},
        message="同步任务已提交，请稍后刷新查看结果",
    )
