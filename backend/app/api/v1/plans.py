from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import require_permissions, get_current_active_user
from app.models.user import User
from app.schemas.plan import (
    PlanCreate,
    PlanUpdate,
    PlanTestcaseAddRequest,
    PlanTestcaseResultUpdate,
)
from app.services.plan_service import PlanService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/plans", tags=["测试计划"])


@router.get("", summary="测试计划列表")
async def get_plans(
    project_id: int | None = Query(None, description="项目 ID"),
    status: str | None = Query(None, description="计划状态"),
    keyword: str | None = Query(None, description="关键字（名称/描述）"),
    order: Literal["asc", "desc"] = Query("desc", description="创建时间排序：asc 正序 / desc 倒序（默认倒序）"),
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:list")),
):
    service = PlanService(db)
    result = await service.get_plans(params, project_id, status, keyword, order)
    return Response.success(data=result.model_dump())


@router.get("/testers", summary="可选测试人（下拉用）")
async def get_tester_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = PlanService(db)
    return Response.success(data=await service.get_tester_candidates())


@router.get("/{plan_id}", summary="测试计划详情")
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:detail", "plan:list")),
):
    service = PlanService(db)
    return Response.success(data=await service.get_plan_detail(plan_id))


@router.post("", summary="新增测试计划")
async def create_plan(
    data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:create")),
):
    service = PlanService(db)
    plan = await service.create_plan(data)
    return Response.success(data=await service.get_plan_detail(plan.id))


@router.put("/{plan_id}", summary="编辑测试计划")
async def update_plan(
    plan_id: int,
    data: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:update")),
):
    service = PlanService(db)
    plan = await service.update_plan(plan_id, data)
    return Response.success(data=await service.get_plan_detail(plan.id))


@router.delete("/{plan_id}", summary="删除测试计划")
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:delete")),
):
    service = PlanService(db)
    await service.delete_plan(plan_id)
    return Response.success(message="删除成功")


@router.get("/{plan_id}/testcases", summary="计划用例列表")
async def get_plan_testcases(
    plan_id: int,
    keyword: str | None = Query(None, description="关键字（用例标题/模块）"),
    result: str | None = Query(None, description="测试结果：pass/fail/blocked/skipped"),
    tester_id: int | None = Query(None, description="测试人 user_id"),
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:case:list")),
):
    service = PlanService(db)
    result_page = await service.list_plan_testcases(
        params, plan_id, keyword, result, tester_id
    )
    return Response.success(data=result_page.model_dump())


@router.get("/{plan_id}/candidates", summary="候选用例（所属项目下未加入本计划的用例）")
async def get_candidates(
    plan_id: int,
    keyword: str | None = Query(None, description="关键字（标题/模块）"),
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:case:add")),
):
    service = PlanService(db)
    result = await service.get_candidates(params, plan_id, keyword)
    return Response.success(data=result.model_dump())


@router.post("/{plan_id}/testcases", summary="批量添加用例到计划")
async def add_testcases(
    plan_id: int,
    data: PlanTestcaseAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:case:add")),
):
    service = PlanService(db)
    result = await service.add_testcases(plan_id, data.testcase_ids)
    return Response.success(data=result, message=f"成功加入 {result['added']} 条用例")


@router.put("/{plan_id}/testcases/{ptc_id}/result", summary="记录/修改测试结果")
async def update_result(
    plan_id: int,
    ptc_id: int,
    data: PlanTestcaseResultUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:case:result")),
):
    service = PlanService(db)
    updated = await service.update_result(
        plan_id,
        ptc_id,
        data.result,
        data.result_desc,
        data.tester_id,
        current_user,
    )
    return Response.success(message="结果已保存")


@router.delete("/{plan_id}/testcases/{ptc_id}", summary="从计划中移除用例")
async def remove_testcase(
    plan_id: int,
    ptc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("plan:case:remove")),
):
    service = PlanService(db)
    await service.remove_testcase(plan_id, ptc_id)
    return Response.success(message="已从计划中移除")
