from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import require_permissions_any, get_current_active_user_any, actor_user_id
from app.models.user import User
from app.schemas.plan import (
    PlanCreate,
    PlanUpdate,
    PlanTestcaseAddRequest,
    PlanTestcaseResultUpdate,
    PlanScheduleCreate,
    PlanScheduleUpdate,
)
from app.services.plan_service import PlanService
from app.services.schedule_service import ScheduleService, trigger_schedule
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
    current_user: User = Depends(require_permissions_any("plan:list")),
):
    service = PlanService(db)
    result = await service.get_plans(params, project_id, status, keyword, order)
    return Response.success(data=result.model_dump())


@router.get("/testers", summary="可选测试人（下拉用）")
async def get_tester_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user_any),
):
    service = PlanService(db)
    return Response.success(data=await service.get_tester_candidates())


@router.get("/{plan_id}", summary="测试计划详情")
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:detail", "plan:list")),
):
    service = PlanService(db)
    return Response.success(data=await service.get_plan_detail(plan_id))


@router.post("", summary="新增测试计划")
async def create_plan(
    data: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:create")),
):
    service = PlanService(db)
    plan = await service.create_plan(data)
    return Response.success(data=await service.get_plan_detail(plan.id))


@router.put("/{plan_id}", summary="编辑测试计划")
async def update_plan(
    plan_id: int,
    data: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:update")),
):
    service = PlanService(db)
    plan = await service.update_plan(plan_id, data)
    return Response.success(data=await service.get_plan_detail(plan.id))


@router.delete("/{plan_id}", summary="删除测试计划")
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:delete")),
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
    current_user: User = Depends(require_permissions_any("plan:case:list")),
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
    current_user: User = Depends(require_permissions_any("plan:case:add")),
):
    service = PlanService(db)
    result = await service.get_candidates(params, plan_id, keyword)
    return Response.success(data=result.model_dump())


@router.post("/{plan_id}/testcases", summary="批量添加用例到计划")
async def add_testcases(
    plan_id: int,
    data: PlanTestcaseAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:add")),
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
    current_user: User = Depends(require_permissions_any("plan:case:result")),
):
    service = PlanService(db)
    updated = await service.update_result(
        plan_id,
        ptc_id,
        data.result,
        data.result_desc,
        current_user,
    )
    return Response.success(message="结果已保存")


@router.delete("/{plan_id}/testcases/{ptc_id}", summary="从计划中移除用例")
async def remove_testcase(
    plan_id: int,
    ptc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:remove")),
):
    service = PlanService(db)
    await service.remove_testcase(plan_id, ptc_id)
    return Response.success(message="已从计划中移除")


@router.post("/{plan_id}/testcases/{ptc_id}/execute", summary="触发自动化执行")
async def execute_auto_case(
    plan_id: int,
    ptc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:execute")),
):
    service = PlanService(db)
    await service.execute_auto_case(plan_id, ptc_id, current_user)
    return Response.success(message="已提交自动化执行，请稍后刷新查看结果")


class BatchExecuteRequest(BaseModel):
    ptc_ids: list[int] = Field(..., description="要执行的计划用例ID列表")


@router.post("/{plan_id}/testcases/batch-execute", summary="批量串行自动化执行")
async def batch_execute_auto_cases(
    plan_id: int,
    body: BatchExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:execute")),
):
    service = PlanService(db)
    await service.execute_auto_cases(plan_id, body.ptc_ids, current_user)
    return Response.success(message=f"已提交批量执行 ({len(body.ptc_ids)} 条用例)，串行执行中，请稍后刷新查看结果")


@router.post("/{plan_id}/testcases/stop-execution", summary="停止批量执行")
async def stop_execution(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:execute")),
):
    service = PlanService(db)
    await service.stop_execution(plan_id)
    return Response.success(message="已请求停止批量执行，剩余未执行的用例将被跳过")


@router.get("/{plan_id}/testcases/{ptc_id}/execution-logs", summary="该计划用例的历史执行日志")
async def list_execution_logs(
    plan_id: int,
    ptc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:list")),
):
    service = PlanService(db)
    logs = await service.list_case_execution_logs(plan_id, ptc_id)
    return Response.success(data=logs)


@router.delete("/{plan_id}/testcases/{ptc_id}/execution-logs/{log_id}", summary="删除历史执行日志（最新一条不允许删除）")
async def delete_execution_log(
    plan_id: int,
    ptc_id: int,
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:execute")),
):
    service = PlanService(db)
    await service.delete_case_execution_log(plan_id, ptc_id, log_id)
    return Response.success(message="删除成功")


@router.get("/{plan_id}/testcases/export", summary="导出计划用例（CSV）")
async def export_plan_testcases(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:list")),
):
    service = PlanService(db)
    csv_content = await service.export_plan_testcases(plan_id)
    from starlette.responses import StreamingResponse
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename=plan_{plan_id}_testcases.csv"},
    )


# ==================== 定时执行 ====================

@router.get("/{plan_id}/schedules", summary="定时执行任务列表")
async def list_plan_schedules(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:schedule:list")),
):
    service = ScheduleService(db)
    return Response.success(data=await service.list_schedules(plan_id))


@router.post("/{plan_id}/schedules", summary="创建定时执行任务")
async def create_plan_schedule(
    plan_id: int,
    data: PlanScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:schedule:create")),
):
    service = ScheduleService(db)
    # created_by 记录归属用户：API 密钥调用时由 actor_user_id 解析为其归属用户
    result = await service.create_schedule(plan_id, data, actor_user_id(current_user))
    return Response.success(data=result, message="定时执行任务创建成功")


@router.put("/{plan_id}/schedules/{schedule_id}", summary="编辑定时执行任务")
async def update_plan_schedule(
    plan_id: int,
    schedule_id: int,
    data: PlanScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:schedule:update")),
):
    service = ScheduleService(db)
    result = await service.update_schedule(plan_id, schedule_id, data)
    return Response.success(data=result, message="更新成功")


@router.patch("/{plan_id}/schedules/{schedule_id}/toggle", summary="启用/停用定时执行任务")
async def toggle_plan_schedule(
    plan_id: int,
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:schedule:update")),
):
    service = ScheduleService(db)
    result = await service.toggle_schedule(plan_id, schedule_id)
    return Response.success(data=result, message="已启用" if result["enabled"] else "已停用")


@router.delete("/{plan_id}/schedules/{schedule_id}", summary="删除定时执行任务")
async def delete_plan_schedule(
    plan_id: int,
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:schedule:delete")),
):
    service = ScheduleService(db)
    await service.delete_schedule(plan_id, schedule_id)
    return Response.success(message="删除成功")


@router.post("/{plan_id}/schedules/{schedule_id}/run-now", summary="立即执行一轮定时任务")
async def run_schedule_now(
    plan_id: int,
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:case:execute")),
):
    # 校验任务归属（plan_id/schedule_id）
    service = ScheduleService(db)
    await service.get_schedule(plan_id, schedule_id)
    await trigger_schedule(schedule_id, manual=True)
    return Response.success(message="已提交定时执行（立即触发一轮），请稍后刷新查看结果")
