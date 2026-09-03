from datetime import datetime
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="项目编码")
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: str | None = Field(None, description="项目描述")
    owner_id: int | None = Field(None, description="负责人 user_id")
    is_active: bool = True
    auto_root_path: str | None = Field(None, max_length=500, description="自动化测试根路径（pytest tests 目录）")
    python_path: str | None = Field(None, max_length=500, description="Python 解释器路径，如 python 或 D:\\anaconda3\\python.exe")


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    owner_id: int | None = None
    is_active: bool | None = None
    auto_root_path: str | None = None
    python_path: str | None = None


class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
