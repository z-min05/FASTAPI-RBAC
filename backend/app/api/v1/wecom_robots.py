from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.wecom_robot import WecomRobotCreate, WecomRobotUpdate
from app.services.wecom_service import WecomRobotService, _to_response
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/wecom-robots", tags=["企业微信群机器人"])


@router.get("/options", summary="机器人下拉选项（仅登录，供测试计划绑定）")
async def list_robot_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = WecomRobotService(db)
    data = await service.list_options()
    return Response.success(data=data)


@router.get("", summary="企业微信群机器人列表")
async def list_robots(
    params: PaginationParams = Depends(),
    keyword: str | None = Query(None, description="关键字（名称）"),
    enabled: bool | None = Query(None, description="启用状态过滤"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("wecom-robot:list")),
):
    service = WecomRobotService(db)
    result = await service.paginate(params, keyword, enabled)
    items = [_to_response(r) for r in result.items]
    return Response.success(data={
        "items": items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    })


@router.get("/{robot_id}", summary="企业微信群机器人详情")
async def get_robot(
    robot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("wecom-robot:list")),
):
    service = WecomRobotService(db)
    robot = await service.get(robot_id)
    return Response.success(data=_to_response(robot))


@router.post("", summary="新增企业微信群机器人")
async def create_robot(
    data: WecomRobotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("wecom-robot:create")),
):
    service = WecomRobotService(db)
    robot = await service.create(data, current_user.id)
    return Response.success(data=_to_response(robot), message="新增成功")


@router.put("/{robot_id}", summary="编辑企业微信群机器人")
async def update_robot(
    robot_id: int,
    data: WecomRobotUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("wecom-robot:update")),
):
    service = WecomRobotService(db)
    robot = await service.update(robot_id, data)
    return Response.success(data=_to_response(robot), message="保存成功")


@router.delete("/{robot_id}", summary="删除企业微信群机器人")
async def delete_robot(
    robot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("wecom-robot:delete")),
):
    service = WecomRobotService(db)
    await service.delete(robot_id)
    return Response.success(message="删除成功")


@router.post("/{robot_id}/test", summary="发送测试消息")
async def test_robot(
    robot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("wecom-robot:update")),
):
    service = WecomRobotService(db)
    robot = await service.get(robot_id)
    ok, err = await WecomRobotService.send_test(robot)
    if not ok:
        return Response.error(message=f"发送失败：{err}")
    return Response.success(message="测试消息发送成功")
