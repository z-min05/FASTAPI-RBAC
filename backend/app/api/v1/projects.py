from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import require_permissions_any, get_current_active_user_any
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.schemas.project_env import (
    EnvCreateRequest,
    EnvRenameRequest,
    EnvSaveRequest,
    EnvUploadRequest,
)
from app.services.project_service import ProjectService
from app.services.project_init_service import ProjectInitService
from app.services.project_env_service import ProjectEnvService
from app.core.pagination import PaginationParams, PaginatedResponse
from app.core.response import Response

router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.get("", summary="项目列表")
async def get_projects(
    keyword: str | None = Query(None, description="关键字（编码/名称）"),
    is_active: bool | None = Query(None, description="启用状态"),
    order: Literal["asc", "desc"] = Query("desc", description="创建时间排序：asc 正序 / desc 倒序（默认倒序）"),
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:list")),
):
    service = ProjectService(db)
    result = await service.get_projects(params, keyword, is_active, order)
    raw = result.model_dump()
    raw["items"] = [ProjectResponse.model_validate(p).model_dump() for p in result.items]
    return Response.success(data=raw)


@router.get("/all", summary="全部启用项目（下拉用）")
async def get_all_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:list")),
):
    service = ProjectService(db)
    projects = await service.get_all_projects()
    return Response.success(
        data=[ProjectResponse.model_validate(p).model_dump() for p in projects]
    )


@router.get("/owners", summary="可选负责人（下拉用）")
async def get_owner_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user_any),
):
    service = ProjectService(db)
    return Response.success(data=await service.get_owner_candidates())


@router.get("/code-template", summary="下载项目自动化模版(zip)")
async def download_project_code_template(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:template")),
):
    service = ProjectInitService(db)
    data = await service.get_code_template()
    return Response.success(data=data)


@router.get("/{project_id}", summary="项目详情")
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:detail")),
):
    service = ProjectService(db)
    project = await service.get_project(project_id)
    return Response.success(data=ProjectResponse.model_validate(project).model_dump())


@router.post("", summary="新增项目")
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:create")),
):
    service = ProjectService(db)
    project = await service.create_project(data)
    return Response.success(data=ProjectResponse.model_validate(project).model_dump())


@router.put("/{project_id}", summary="编辑项目")
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:update")),
):
    service = ProjectService(db)
    project = await service.update_project(project_id, data)
    return Response.success(data=ProjectResponse.model_validate(project).model_dump())


@router.post("/{project_id}/code", summary="上传自动化代码包并初始化")
async def upload_project_code(
    project_id: int,
    file: UploadFile = File(..., description="自动化代码压缩包（zip），顶层需为唯一的项目文件夹且内含 tests 目录"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:init")),
):
    service = ProjectInitService(db)
    data = await service.upload_and_dispatch(project_id, file, current_user.id)
    return Response.success(data=data, message="代码初始化任务已提交，请稍后刷新查看结果")


@router.post("/{project_id}/code/install", summary="重装项目依赖")
async def reinstall_project_code(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:init")),
):
    service = ProjectInitService(db)
    data = await service.reinstall_and_dispatch(project_id)
    return Response.success(data=data, message="依赖重装任务已提交，请稍后刷新查看结果")


@router.get("/{project_id}/auto-code/zip", summary="打包下载项目自动化代码(zip)")
async def download_project_auto_code(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:code:download")),
):
    service = ProjectInitService(db)
    zip_path, filename = await service.stage_auto_code_zip(project_id)
    # 响应发送完成后再删除临时包，避免占用磁盘
    background_tasks.add_task(Path(zip_path).unlink, missing_ok=True)
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
    )


@router.delete("/{project_id}", summary="删除项目")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:delete")),
):
    service = ProjectService(db)
    await service.delete_project(project_id)
    return Response.success(message="删除成功")


# ==================== 自动化测试环境管理 ====================
# 说明：环境快照存于 {项目根}/.envs/<name>.env，生效环境为 {项目根}/.env；
# 「当前生效环境」由内容比对判定。注意 /envs/diff 必须注册在 /envs/{name} 之前。


@router.get("/{project_id}/envs", summary="自动化测试环境列表")
async def list_project_envs(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:list")),
):
    service = ProjectEnvService(db)
    return Response.success(data=await service.list_envs(project_id))


@router.get("/{project_id}/envs/diff", summary="环境差异对比（@active 表示当前生效 .env）")
async def diff_project_envs(
    project_id: int,
    left: str = Query(..., description="左侧环境名或 @active"),
    right: str = Query(..., description="右侧环境名或 @active"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:list")),
):
    service = ProjectEnvService(db)
    return Response.success(data=await service.diff_envs(project_id, left, right))


@router.post("/{project_id}/envs", summary="新建环境")
async def create_project_env(
    project_id: int,
    data: EnvCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:create")),
):
    service = ProjectEnvService(db)
    result = await service.create_env(
        project_id, data.name, data.source, data.content, data.remark, current_user.id
    )
    return Response.success(data=result, message=f"环境 {data.name} 已创建")


@router.post("/{project_id}/envs/upload", summary="上传文件作为新环境（环境名取文件名）")
async def upload_project_env(
    project_id: int,
    data: EnvUploadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:create")),
):
    service = ProjectEnvService(db)
    result = await service.upload_env(
        project_id, data.filename, data.content, data.remark, current_user.id
    )
    return Response.success(data=result, message=f"环境 {result['name']} 已创建")


@router.get("/{project_id}/env", summary="读取当前生效的 .env")
async def get_project_active_env(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:list")),
):
    service = ProjectEnvService(db)
    return Response.success(data=await service.get_active_file(project_id))


@router.put("/{project_id}/env", summary="直接编辑当前生效的 .env")
async def save_project_active_env(
    project_id: int,
    data: EnvSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:update")),
):
    service = ProjectEnvService(db)
    result = await service.save_active_file(project_id, data.content, current_user.id)
    return Response.success(data=result, message="当前生效环境已保存")


@router.get("/{project_id}/envs/{name}", summary="读取环境内容")
async def get_project_env(
    project_id: int,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:list")),
):
    service = ProjectEnvService(db)
    return Response.success(data=await service.get_env(project_id, name))


@router.put("/{project_id}/envs/{name}", summary="保存环境内容")
async def save_project_env(
    project_id: int,
    name: str,
    data: EnvSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:update")),
):
    service = ProjectEnvService(db)
    result = await service.save_env(
        project_id, name, data.content, data.remark, current_user.id
    )
    return Response.success(data=result, message=f"环境 {name} 已保存")


@router.post("/{project_id}/envs/{name}/apply", summary="应用环境（切换当前生效环境）")
async def apply_project_env(
    project_id: int,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:apply")),
):
    service = ProjectEnvService(db)
    result = await service.apply_env(project_id, name)
    return Response.success(data=result, message=f"已切换到环境 {name}")


@router.post("/{project_id}/envs/{name}/rename", summary="重命名环境")
async def rename_project_env(
    project_id: int,
    name: str,
    data: EnvRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:update")),
):
    service = ProjectEnvService(db)
    result = await service.rename_env(project_id, name, data.new_name)
    return Response.success(data=result, message=f"环境已重命名为 {data.new_name}")


@router.delete("/{project_id}/envs/{name}", summary="删除环境")
async def delete_project_env(
    project_id: int,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:delete")),
):
    service = ProjectEnvService(db)
    await service.delete_env(project_id, name)
    return Response.success(message=f"环境 {name} 已删除")


@router.get("/{project_id}/envs/{name}/download", summary="下载环境文件")
async def download_project_env(
    project_id: int,
    name: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("project:env:list")),
):
    service = ProjectEnvService(db)
    tmp_path = await service.export_env_file(project_id, name)
    # 响应发送完成后再删除临时文件
    background_tasks.add_task(Path(tmp_path).unlink, missing_ok=True)
    return FileResponse(
        path=tmp_path,
        media_type="text/plain",
        filename=f"{name}.env",
    )

