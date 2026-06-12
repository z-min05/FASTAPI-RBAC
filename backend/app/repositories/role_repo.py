from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.role import Role
from app.models.user_role import user_roles
from app.models.role_permission import role_permissions
from app.models.role_menu import role_menus
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(Role, db)

    async def get_by_id(self, id: int) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.id == id)
            .options(selectinload(Role.permissions), selectinload(Role.menus))
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Role | None:
        stmt = select(Role).where(Role.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_roles_by_user_id(self, user_id: int) -> list[Role]:
        stmt = (
            select(Role)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def set_role_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        await self.db.execute(
            role_permissions.delete().where(role_permissions.c.role_id == role_id)
        )
        if permission_ids:
            await self.db.execute(
                role_permissions.insert(),
                [{"role_id": role_id, "permission_id": pid} for pid in permission_ids],
            )
        await self.db.flush()

    async def set_role_menus(self, role_id: int, menu_ids: list[int]) -> None:
        await self.db.execute(
            role_menus.delete().where(role_menus.c.role_id == role_id)
        )
        if menu_ids:
            await self.db.execute(
                role_menus.insert(),
                [{"role_id": role_id, "menu_id": mid} for mid in menu_ids],
            )
        await self.db.flush()

    async def get_role_permission_ids(self, role_id: int) -> list[int]:
        stmt = select(role_permissions.c.permission_id).where(
            role_permissions.c.role_id == role_id
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_role_menu_ids(self, role_id: int) -> list[int]:
        stmt = select(role_menus.c.menu_id).where(role_menus.c.role_id == role_id)
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]
