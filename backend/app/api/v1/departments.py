from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.services.department_service import DepartmentService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/departments", tags=["部门管理"])


@router.get("", summary="获取部门列表")
async def get_departments(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("department:list")),
):
    service = DepartmentService(db)
    result = await service.get_departments(params)
    return Response.success(data=result.model_dump())


@router.get("/tree", summary="获取部门树")
async def get_department_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("department:list")),
):
    service = DepartmentService(db)
    tree = await service.get_department_tree()
    return Response.success(data=[item.model_dump() for item in tree])


@router.get("/{dept_id}", summary="获取部门详情")
async def get_department(
    dept_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("department:detail")),
):
    service = DepartmentService(db)
    dept = await service.get_department(dept_id)
    return Response.success(data=DepartmentResponse.model_validate(dept).model_dump())


@router.post("", summary="创建部门")
async def create_department(
    data: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("department:create")),
):
    service = DepartmentService(db)
    dept = await service.create_department(data)
    return Response.success(data=DepartmentResponse.model_validate(dept).model_dump())


@router.put("/{dept_id}", summary="更新部门")
async def update_department(
    dept_id: int,
    data: DepartmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("department:update")),
):
    service = DepartmentService(db)
    dept = await service.update_department(dept_id, data)
    return Response.success(data=DepartmentResponse.model_validate(dept).model_dump())


@router.delete("/{dept_id}", summary="删除部门")
async def delete_department(
    dept_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("department:delete")),
):
    service = DepartmentService(db)
    await service.delete_department(dept_id)
    return Response.success(message="删除成功")
