from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user, require_permissions
from app.models.user import User
from app.schemas.menu import MenuCreate, MenuUpdate, MenuResponse
from app.services.menu_service import MenuService
from app.core.pagination import PaginationParams
from app.core.response import Response

router = APIRouter(prefix="/menus", tags=["菜单管理"])


@router.get("", summary="获取菜单列表")
async def get_menus(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("menu:list")),
):
    service = MenuService(db)
    result = await service.get_menus(params)
    return Response.success(data=result.model_dump())


@router.get("/tree", summary="获取菜单树")
async def get_menu_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("menu:list")),
):
    service = MenuService(db)
    tree = await service.get_menu_tree()
    return Response.success(data=[item.model_dump() for item in tree])


@router.get("/{menu_id}", summary="获取菜单详情")
async def get_menu(
    menu_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("menu:detail")),
):
    service = MenuService(db)
    menu = await service.get_menu(menu_id)
    return Response.success(data=MenuResponse.model_validate(menu).model_dump())


@router.post("", summary="创建菜单")
async def create_menu(
    data: MenuCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("menu:create")),
):
    service = MenuService(db)
    menu = await service.create_menu(data)
    return Response.success(data=MenuResponse.model_validate(menu).model_dump())


@router.put("/{menu_id}", summary="更新菜单")
async def update_menu(
    menu_id: int,
    data: MenuUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("menu:update")),
):
    service = MenuService(db)
    menu = await service.update_menu(menu_id, data)
    return Response.success(data=MenuResponse.model_validate(menu).model_dump())


@router.delete("/{menu_id}", summary="删除菜单")
async def delete_menu(
    menu_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("menu:delete")),
):
    service = MenuService(db)
    await service.delete_menu(menu_id)
    return Response.success(message="删除成功")
