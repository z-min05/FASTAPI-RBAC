from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import require_permissions_any
from app.models.user import User
from app.schemas.common import IDListRequest
from app.schemas.testcase import TestCaseCreate, TestCaseUpdate, TestCaseResponse
from app.services.testcase_service import TestCaseService
from app.services.testcase_sync_service import ensure_sync_ready, dispatch_project_sync
from app.core.pagination import PaginationParams, PaginatedResponse
from app.core.response import Response
from app.exceptions import BadRequestException

router = APIRouter(prefix="/testcases", tags=["用例管理"])


@router.get("", summary="用例列表")
async def get_testcases(
    project_id: int | None = Query(None, description="项目 ID"),
    module: str | None = Query(None, description="模块名称（模糊匹配）"),
    module_id: int | None = Query(None, description="模块 ID"),
    include_children: bool = Query(True, description="module_id 是否包含其子模块"),
    priority: str | None = Query(None, description="优先级 P0-P3"),
    status: str | None = Query(None, description="状态"),
    source: str | None = Query(None, description="来源"),
    keyword: str | None = Query(None, description="关键字（标题/模块）"),
    order: Literal["asc", "desc"] = Query("desc", description="创建时间排序：asc 正序 / desc 倒序（默认倒序）"),
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:list")),
):
    service = TestCaseService(db)
    result = await service.get_testcases(
        params,
        project_id=project_id,
        module=module,
        priority=priority,
        status=status,
        source=source,
        keyword=keyword,
        module_id=module_id,
        include_children=include_children,
        order=order,
    )
    raw = result.model_dump()
    return Response.success(data=raw)


@router.get("/modules", summary="模块列表")
async def get_modules(
    project_id: int | None = Query(None, description="项目 ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:list")),
):
    service = TestCaseService(db)
    modules = await service.get_modules(project_id)
    return Response.success(data=modules)


@router.post("/batch-delete", summary="批量删除用例")
async def batch_delete_testcases(
    data: IDListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:delete")),
):
    service = TestCaseService(db)
    count = await service.delete_testcases(data.ids)
    return Response.success(message=f"已删除 {count} 条用例")


class SyncRequest(BaseModel):
    project_id: int


@router.post("/sync", summary="同步项目自动化用例")
async def sync_testcases(
    data: SyncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:sync")),
):
    """扫描项目自动化根路径下的 pytest 用例并补齐入库（只新增，异步下发）"""
    await ensure_sync_ready(db, data.project_id)
    dispatch_project_sync(data.project_id)
    return Response.success(message="已下发同步任务，请稍后刷新查看用例情况")


@router.get("/import-template", summary="导入模板下载(xlsx)")
async def import_template(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:import")),
):
    import base64

    service = TestCaseService(db)
    content = await service.get_import_template()
    return Response.success(data={
        "filename": "testcase_import_template.xlsx",
        "content": base64.b64encode(content).decode("ascii"),
        "is_base64": True,
    })


class ImportRequest(BaseModel):
    content: str
    format: str = "csv"  # csv | xlsx（xlsx 时 content 为 base64）


@router.post("/import", summary="导入用例(CSV/xlsx)")
async def import_testcases(
    data: ImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:import")),
):
    import base64

    service = TestCaseService(db)
    if data.format == "xlsx":
        try:
            raw = base64.b64decode(data.content)
        except Exception:
            raise BadRequestException("xlsx 内容解码失败")
        result = await service.import_xlsx(raw)
    else:
        result = await service.import_csv(data.content)
    return Response.success(data=result, message="导入完成")


@router.post("/export", summary="导出用例(CSV)")
async def export_testcases(
    project_id: int | None = Query(None, description="项目 ID"),
    module: str | None = Query(None, description="模块名称（模糊匹配）"),
    module_id: int | None = Query(None, description="模块 ID"),
    include_children: bool = Query(True, description="module_id 是否包含其子模块"),
    priority: str | None = Query(None, description="优先级"),
    status: str | None = Query(None, description="状态"),
    source: str | None = Query(None, description="来源"),
    keyword: str | None = Query(None, description="关键字"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:export")),
):
    service = TestCaseService(db)
    content = await service.export_csv(
        project_id,
        module,
        priority,
        status,
        source,
        keyword,
        module_id,
        include_children,
    )
    filename = f"testcases_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    return Response.success(data={"filename": filename, "content": content})


@router.get("/{testcase_id}", summary="用例详情")
async def get_testcase(
    testcase_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:detail")),
):
    service = TestCaseService(db)
    tc = await service.get_testcase(testcase_id)
    project_map = await service._get_project_map([tc.project_id])
    return Response.success(data=service._to_response(tc, project_map))


@router.post("", summary="新增用例")
async def create_testcase(
    data: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:create")),
):
    service = TestCaseService(db)
    tc = await service.create_testcase(data)
    project_map = await service._get_project_map([tc.project_id])
    return Response.success(data=service._to_response(tc, project_map))


@router.put("/{testcase_id}", summary="编辑用例")
async def update_testcase(
    testcase_id: int,
    data: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:update")),
):
    service = TestCaseService(db)
    tc = await service.update_testcase(testcase_id, data)
    project_map = await service._get_project_map([tc.project_id])
    return Response.success(data=service._to_response(tc, project_map))


@router.delete("/{testcase_id}", summary="删除用例")
async def delete_testcase(
    testcase_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:delete")),
):
    service = TestCaseService(db)
    await service.delete_testcase(testcase_id)
    return Response.success(message="删除成功")
