from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.department_repo import DepartmentRepository
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentTreeResponse
from app.core.pagination import PaginationParams, PaginatedResponse
from app.exceptions import NotFoundException
from app.utils.helpers import build_tree


class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dept_repo = DepartmentRepository(db)

    async def get_department(self, dept_id: int) -> Department:
        dept = await self.dept_repo.get_by_id(dept_id)
        if not dept:
            raise NotFoundException("部门不存在")
        return dept

    async def get_departments(self, params: PaginationParams) -> PaginatedResponse:
        return await self.dept_repo.get_paginated(params)

    async def get_department_tree(self) -> list[DepartmentTreeResponse]:
        depts = await self.dept_repo.get_all_departments()
        dept_dicts = [
            {"id": d.id, "name": d.name, "code": d.code, "parent_id": d.parent_id,
             "sort": d.sort, "leader": d.leader, "phone": d.phone, "status": d.status,
             "created_at": d.created_at, "updated_at": d.updated_at}
            for d in depts
        ]
        tree = build_tree(dept_dicts, parent_key="parent_id")
        return [DepartmentTreeResponse(**item) for item in tree]

    async def create_department(self, data: DepartmentCreate) -> Department:
        dept = Department(**data.model_dump())
        return await self.dept_repo.create(dept)

    async def update_department(self, dept_id: int, data: DepartmentUpdate) -> Department:
        update_data = data.model_dump(exclude_unset=True)
        dept = await self.dept_repo.update(dept_id, update_data)
        if not dept:
            raise NotFoundException("部门不存在")
        return dept

    async def delete_department(self, dept_id: int) -> None:
        if not await self.dept_repo.delete(dept_id):
            raise NotFoundException("部门不存在")
