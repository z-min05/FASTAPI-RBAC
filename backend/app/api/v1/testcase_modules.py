from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import Response
from app.db.session import get_db
from app.dependency import require_permissions_any
from app.models.user import User
from app.schemas.testcase_module import (
    TestCaseModuleCreate,
    TestCaseModuleResponse,
    TestCaseModuleUpdate,
)
from app.services.testcase_module_service import TestCaseModuleService

router = APIRouter(prefix="/testcase-modules", tags=["用例模块"])


@router.get("/tree", summary="模块树")
async def get_module_tree(
    project_id: int = Query(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:list")),
):
    """取项目下的完整模块树（含 is_leaf / module_path / 用例数）

    读操作复用 testcase:list：模块树与用例列表属于同一个页面。
    """
    service = TestCaseModuleService(db)
    return Response.success(data=await service.get_tree(project_id))


@router.get("/{module_id}", summary="模块详情")
async def get_module(
    module_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:list")),
):
    service = TestCaseModuleService(db)
    return Response.success(data=await service.get_module_detail(module_id))


@router.post("", summary="新建模块")
async def create_module(
    data: TestCaseModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:module:create")),
):
    service = TestCaseModuleService(db)
    node = await service.create_module(data)
    return Response.success(
        data=TestCaseModuleResponse.model_validate(node).model_dump(),
        message="创建成功",
    )


@router.put("/{module_id}", summary="编辑模块")
async def update_module(
    module_id: int,
    data: TestCaseModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:module:update")),
):
    service = TestCaseModuleService(db)
    node = await service.update_module(module_id, data)
    return Response.success(
        data=TestCaseModuleResponse.model_validate(node).model_dump(),
        message="更新成功",
    )


@router.delete("/{module_id}", summary="删除模块")
async def delete_module(
    module_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("testcase:module:delete")),
):
    service = TestCaseModuleService(db)
    await service.delete_module(module_id)
    return Response.success(message="删除成功")
