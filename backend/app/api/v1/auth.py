from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, RefreshTokenRequest
from app.services.auth_service import AuthService
from app.core.response import Response
from app.core.rbac import get_user_menus
from app.core.pagination import PaginationParams
from app.dependency import get_current_active_user
from app.models.user import User
from app.utils.helpers import build_tree

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", summary="登录")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    token = await service.login(data)
    return Response.success(data=token.model_dump())


@router.post("/register", summary="注册")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    token = await service.register(data)
    return Response.success(data=token.model_dump())


@router.post("/refresh", summary="刷新令牌")
async def refresh_token(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    token = await service.refresh_token(data)
    return Response.success(data=token.model_dump())


@router.get("/menus", summary="获取当前用户菜单")
async def get_menus(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    menus = await get_user_menus(db, current_user.id)
    tree = build_tree(menus, parent_key="parent_id")
    return Response.success(data=tree)
