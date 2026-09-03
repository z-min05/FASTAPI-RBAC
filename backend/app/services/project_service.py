from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.project_repo import ProjectRepository
from app.repositories.plan_repo import PlanRepository
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.core.pagination import PaginationParams, PaginatedResponse
from app.exceptions import NotFoundException, ConflictException, BadRequestException
from app.services.auto_file_service import validate_root_path


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.project_repo = ProjectRepository(db)

    async def get_project(self, project_id: int) -> Project:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException("项目不存在")
        return project

    async def get_projects(
        self,
        params: PaginationParams,
        keyword: str | None = None,
        is_active: bool | None = None,
        order: str = "desc",
    ) -> PaginatedResponse:
        return await self.project_repo.get_paginated(params, keyword, is_active, order)

    async def get_all_projects(self) -> list[Project]:
        """全部启用中的项目（下拉用）"""
        return await self.project_repo.get_active_all()

    async def get_owner_candidates(self) -> list[dict]:
        """可选负责人（启用中的用户，下拉用）"""
        result = await self.db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        )
        return [
            {"id": u.id, "username": u.username, "nickname": u.nickname or u.username}
            for u in result.scalars().all()
        ]

    async def create_project(self, data: ProjectCreate) -> Project:
        if await self.project_repo.get_by_code(data.code):
            raise ConflictException("项目编码已存在")
        if data.auto_root_path:
            ok, msg = validate_root_path(data.auto_root_path)
            if not ok:
                raise BadRequestException(msg)
        project = Project(**data.model_dump())
        return await self.project_repo.create(project)

    async def update_project(self, project_id: int, data: ProjectUpdate) -> Project:
        update_data = data.model_dump(exclude_unset=True)
        if update_data.get("code"):
            existing = await self.project_repo.get_by_code(update_data["code"])
            if existing and existing.id != project_id:
                raise ConflictException("项目编码已存在")
        if "auto_root_path" in update_data and update_data["auto_root_path"]:
            ok, msg = validate_root_path(update_data["auto_root_path"])
            if not ok:
                raise BadRequestException(msg)
        project = await self.project_repo.update(project_id, update_data)
        if not project:
            raise NotFoundException("项目不存在")
        return project

    async def delete_project(self, project_id: int) -> None:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException("项目不存在")
        count = await self.project_repo.count_testcases(project_id)
        if count > 0:
            raise ConflictException(f"该项目下存在 {count} 条用例，请先删除用例")
        plan_count = await PlanRepository(self.db).count_by_project(project_id)
        if plan_count > 0:
            raise ConflictException(f"该项目下存在 {plan_count} 个测试计划，请先删除计划")
        await self.project_repo.delete(project_id)
