from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependency import require_permissions_any
from app.models.user import User
from app.services.dashboard_service import DashboardService
from app.core.response import Response

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get("/stats", summary="获取仪表盘统计")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions_any("plan:list")),
):
    service = DashboardService(db)
    data = await service.get_stats()
    return Response.success(data=data)