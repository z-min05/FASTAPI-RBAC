import base64
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, RefreshTokenRequest, CaptchaResponse
from app.services.auth_service import AuthService
from app.core.response import Response
from app.core.rbac import get_user_menus
from app.core.pagination import PaginationParams
from app.dependency import get_current_active_user
from app.models.user import User
from app.utils.helpers import build_tree
from app.utils.captcha import generate_captcha
from app.utils.redis import get_redis

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/captcha", summary="获取图片验证码")
async def get_captcha():
    code, img_bytes = generate_captcha()
    captcha_key = str(uuid.uuid4())
    rd = await get_redis()
    await rd.set(captcha_key, code, ex=300)  # 5分钟过期
    captcha_image = base64.b64encode(img_bytes).decode("utf-8")
    return Response.success(data=CaptchaResponse(
        captcha_key=captcha_key,
        captcha_image=f"data:image/png;base64,{captcha_image}",
    ).model_dump())


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
