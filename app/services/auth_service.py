from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import UserRepository
from app.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, RefreshTokenRequest
from app.exceptions import UnauthorizedException, ConflictException


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_username(data.username)
        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedException("用户名或密码错误")
        if not user.is_active:
            raise UnauthorizedException("用户已被禁用")

        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def register(self, data: RegisterRequest) -> TokenResponse:
        if await self.user_repo.get_by_username(data.username):
            raise ConflictException("用户名已存在")
        if await self.user_repo.get_by_email(data.email):
            raise ConflictException("邮箱已存在")

        user = await self.user_repo.create(
            type("UserObj", (), {
                "username": data.username,
                "email": data.email,
                "hashed_password": get_password_hash(data.password),
                "nickname": data.nickname,
                "phone": data.phone,
            })()
        )

        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def refresh_token(self, data: RefreshTokenRequest) -> TokenResponse:
        try:
            payload = decode_token(data.refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedException("无效的刷新令牌")
            user_id = payload.get("sub")
        except Exception:
            raise UnauthorizedException("无效或已过期的刷新令牌")

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("用户不存在或已被禁用")

        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
