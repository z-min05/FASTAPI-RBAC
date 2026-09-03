from fastapi import APIRouter, Depends, Query
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import require_permissions, get_current_active_user
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.project_service import ProjectService
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
    current_user: User = Depends(require_permissions("project:list")),
):
    service = ProjectService(db)
    result = await service.get_projects(params, keyword, is_active, order)
    raw = result.model_dump()
    raw["items"] = [ProjectResponse.model_validate(p).model_dump() for p in result.items]
    return Response.success(data=raw)


@router.get("/all", summary="全部启用项目（下拉用）")
async def get_all_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("project:list")),
):
    service = ProjectService(db)
    projects = await service.get_all_projects()
    return Response.success(
        data=[ProjectResponse.model_validate(p).model_dump() for p in projects]
    )


@router.get("/owners", summary="可选负责人（下拉用）")
async def get_owner_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = ProjectService(db)
    return Response.success(data=await service.get_owner_candidates())


@router.get("/{project_id}", summary="项目详情")
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("project:detail")),
):
    service = ProjectService(db)
    project = await service.get_project(project_id)
    return Response.success(data=ProjectResponse.model_validate(project).model_dump())


@router.post("", summary="新增项目")
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("project:create")),
):
    service = ProjectService(db)
    project = await service.create_project(data)
    return Response.success(data=ProjectResponse.model_validate(project).model_dump())


@router.put("/{project_id}", summary="编辑项目")
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("project:update")),
):
    service = ProjectService(db)
    project = await service.update_project(project_id, data)
    return Response.success(data=ProjectResponse.model_validate(project).model_dump())


@router.delete("/{project_id}", summary="删除项目")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("project:delete")),
):
    service = ProjectService(db)
    await service.delete_project(project_id)
    return Response.success(message="删除成功")
