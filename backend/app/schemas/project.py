from datetime import datetime
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="项目编码")
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: str | None = Field(None, description="项目描述")
    owner_id: int | None = Field(None, description="负责人 user_id")
    is_active: bool = True


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    owner_id: int | None = None
    is_active: bool | None = None


class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
