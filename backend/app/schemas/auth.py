from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    captcha_key: str = Field(..., description="验证码唯一标识")
    captcha_code: str = Field(..., min_length=1, max_length=10, description="验证码")


class CaptchaResponse(BaseModel):
    captcha_key: str = Field(..., description="验证码唯一标识")
    captcha_image: str = Field(..., description="Base64 编码的验证码图片")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100)
    nickname: str | None = None
    phone: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str
