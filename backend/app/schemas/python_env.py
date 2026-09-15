from pydantic import BaseModel, Field


class PythonEnvCreate(BaseModel):
    """新增环境：名称即目录名，只允许字母/数字/下划线/中划线"""
    name: str = Field(
        ..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$",
        description="环境名（同时作为目录名，创建后不可修改）",
    )
    python_version: str = Field(..., min_length=1, max_length=20, description="Python 版本，如 3.11")
    description: str | None = Field(None, max_length=500, description="备注")


class PythonEnvUpdate(BaseModel):
    """编辑环境：name / python_version 创建后不可变，仅允许修改备注"""
    description: str | None = Field(None, max_length=500, description="备注")
