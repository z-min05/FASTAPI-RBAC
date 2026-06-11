from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.menu_repo import MenuRepository
from app.models.menu import Menu
from app.schemas.menu import MenuCreate, MenuUpdate, MenuTreeResponse
from app.core.pagination import PaginationParams, PaginatedResponse
from app.exceptions import NotFoundException, ConflictException
from app.utils.helpers import build_tree


class MenuService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.menu_repo = MenuRepository(db)

    async def get_menu(self, menu_id: int) -> Menu:
        menu = await self.menu_repo.get_by_id(menu_id)
        if not menu:
            raise NotFoundException("菜单不存在")
        return menu

    async def get_menus(self, params: PaginationParams) -> PaginatedResponse:
        return await self.menu_repo.get_paginated(params)

    async def get_menu_tree(self) -> list[MenuTreeResponse]:
        menus = await self.menu_repo.get_all_menus()
        menu_dicts = [
            {"id": m.id, "name": m.name, "path": m.path, "component": m.component,
             "icon": m.icon, "menu_type": m.menu_type, "parent_id": m.parent_id,
             "sort": m.sort, "visible": m.visible, "permission": m.permission,
             "created_at": m.created_at, "updated_at": m.updated_at}
            for m in menus
        ]
        tree = build_tree(menu_dicts, parent_key="parent_id")
        return [MenuTreeResponse(**item) for item in tree]

    async def create_menu(self, data: MenuCreate) -> Menu:
        menu = Menu(**data.model_dump())
        return await self.menu_repo.create(menu)

    async def update_menu(self, menu_id: int, data: MenuUpdate) -> Menu:
        update_data = data.model_dump(exclude_unset=True)
        menu = await self.menu_repo.update(menu_id, update_data)
        if not menu:
            raise NotFoundException("菜单不存在")
        return menu

    async def delete_menu(self, menu_id: int) -> None:
        if not await self.menu_repo.delete(menu_id):
            raise NotFoundException("菜单不存在")
