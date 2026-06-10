from datetime import datetime
from pydantic import BaseModel, Field


class UserBase(BaseModel):
    username: str
    email: str
    nickname: str | None = None
    phone: str | None = None
    avatar: str | None = None
    is_active: bool = True
    department_id: int | None = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(...)
    password: str = Field(..., min_length=6, max_length=100)
    nickname: str | None = None
    phone: str | None = None
    department_id: int | None = None
    role_ids: list[int] | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    nickname: str | None = None
    phone: str | None = None
    avatar: str | None = None
    is_active: bool | None = None
    department_id: int | None = None
    role_ids: list[int] | None = None


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserWithRolesResponse(UserResponse):
    roles: list["RoleBriefResponse"] = []

    model_config = {"from_attributes": True}


from app.schemas.role import RoleBriefResponse
UserWithRolesResponse.model_rebuild()
