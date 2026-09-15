from datetime import datetime
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="项目编码")
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: str | None = Field(None, description="项目描述")
    owner_id: int | None = Field(None, description="负责人 user_id")
    is_active: bool = True
    python_path: str | None = Field(None, max_length=500, description="Python 解释器路径，如 python 或 D:\\anaconda3\\python.exe")


class ProjectCreate(ProjectBase):
    """新增项目。自动化根路径不在创建时填写，由代码包初始化任务自动推导写入。"""


class ProjectUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    owner_id: int | None = None
    is_active: bool | None = None
    python_path: str | None = None


class ProjectResponse(ProjectBase):
    id: int
    # auto_root_path 为只读派生字段：= {配置的全局根目录}/{压缩包顶层目录名}/tests，
    # 由代码包初始化任务写入，前端不可修改
    auto_root_path: str | None = Field(None, description="自动化测试根路径（初始化后自动生成）")

    # ---------- 自动化代码初始化状态（只读） ----------
    code_init_status: str = Field("none", description="none/pending/extracting/installing/ready/failed")
    code_init_error: str | None = None
    code_init_log: str | None = None
    code_init_at: datetime | None = None
    code_init_by: int | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
