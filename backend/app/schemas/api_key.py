from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., max_length=100, description="密钥名称")
    role_id: int = Field(..., description="关联角色 ID（必填）")
    expires_at: Optional[datetime] = Field(None, description="过期时间，null 永不过期")


class ApiKeyStatusUpdate(BaseModel):
    """启用/禁用 API 密钥"""
    is_active: bool = Field(..., description="是否启用")


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    role_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiKeyCreatedResponse(ApiKeyResponse):
    """创建成功后返回，包含完整密钥（仅此一次）"""
    full_key: str = Field(..., description="完整密钥，仅创建时返回一次")


class ApiKeyRegenerateResponse(BaseModel):
    full_key: str
    message: str = "密钥已重新生成"