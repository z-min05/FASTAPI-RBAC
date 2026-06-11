from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.log import OperationLogResponse
from app.services.log_service import LogService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/logs", tags=["操作日志"])


@router.get("", summary="获取操作日志列表")
async def get_logs(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("log:list")),
):
    service = LogService(db)
    result = await service.get_logs(params)
    return Response.success(data=result.model_dump())


@router.get("/user/{user_id}", summary="获取指定用户的操作日志")
async def get_user_logs(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("log:list")),
):
    service = LogService(db)
    logs = await service.get_user_logs(user_id)
    return Response.success(data=[OperationLogResponse.model_validate(l).model_dump() for l in logs])
