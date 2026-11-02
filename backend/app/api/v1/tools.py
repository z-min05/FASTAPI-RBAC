"""工具管理路由

- 工具由「压缩包（zip）」与「README 文档（md）」组成，上传时一并提交。
- 列表/详情/上传/下载/删除均走 RBAC 细粒度授权（tool:*）。
- 删除会同时删除数据库记录与磁盘上的压缩包、README 文件。
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginationParams
from app.core.response import Response
from app.db.session import get_db
from app.dependency import require_permissions
from app.models.user import User
from app.services.tool_service import ToolService, to_response

router = APIRouter(prefix="/tools", tags=["工具管理"])


@router.get("", summary="工具列表")
async def list_tools(
    params: PaginationParams = Depends(),
    keyword: str | None = Query(None, description="关键字（工具名称）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("tool:list")),
):
    service = ToolService(db)
    result = await service.paginate(params, keyword)
    name_map = await service.user_name_map({t.created_by for t in result.items})
    items = [to_response(t, name_map.get(t.created_by)) for t in result.items]
    return Response.success(data={
        "items": items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    })


@router.post("", summary="上传工具（压缩包 + README）")
async def upload_tool(
    name: str = Form(..., min_length=1, max_length=200, description="工具名称"),
    package: UploadFile = File(..., description="工具压缩包（zip）"),
    readme: UploadFile = File(..., description="README 文档（md）"),
    description: str | None = Form(None, description="工具描述"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("tool:create")),
):
    service = ToolService(db)
    tool = await service.create(name, description, package, readme, current_user.id)
    return Response.success(
        data=to_response(tool, current_user.nickname or current_user.username),
        message="上传成功",
    )


@router.get("/{tool_id}", summary="工具详情（含 README 内容）")
async def get_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("tool:list")),
):
    service = ToolService(db)
    tool = await service.get(tool_id)
    name_map = await service.user_name_map({tool.created_by})
    return Response.success(data=to_response(
        tool, name_map.get(tool.created_by), readme_content=service.read_readme(tool)
    ))


@router.get("/{tool_id}/download", summary="下载工具压缩包")
async def download_tool_package(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("tool:download")),
):
    service = ToolService(db)
    tool = await service.get(tool_id)
    return FileResponse(
        path=service.package_abs_path(tool),
        media_type="application/zip",
        filename=tool.package_filename,
    )


@router.delete("/{tool_id}", summary="删除工具（同时删除磁盘文件）")
async def delete_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("tool:delete")),
):
    service = ToolService(db)
    await service.delete(tool_id)
    return Response.success(message="删除成功")
