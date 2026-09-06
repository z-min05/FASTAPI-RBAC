from datetime import datetime
from pydantic import BaseModel, Field

# 允许的枚举值（导入导出校验使用）
ALLOWED_PRIORITIES = ["P0", "P1", "P2", "P3"]
ALLOWED_STATUS = ["draft", "reviewed", "archived"]
ALLOWED_CASE_TYPES = [
    "function", "interface", "performance", "compatibility", "security",
]


class TestCaseBase(BaseModel):
    project_id: int = Field(..., description="所属项目")
    title: str = Field(..., min_length=1, max_length=200)
    module: str = Field(..., min_length=1, max_length=50)
    priority: str = Field("P1", pattern="^P[0-3]$")
    case_type: str = Field("function")
    source: str | None = Field(None, max_length=50)
    precondition: str | None = None
    steps: str | None = None
    expected_result: str = Field(..., min_length=1)
    status: str = Field("draft")
    tags: str | None = Field(None, max_length=200)
    module_code: str | None = Field(None, max_length=100, description="模块编码（pytest 文件名，不含 .py，需以 test_ 开头）")
    case_code: str | None = Field(None, max_length=100, description="用例编码（pytest 函数名，需以 test_ 开头）")


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(BaseModel):
    project_id: int | None = None
    title: str | None = Field(None, min_length=1, max_length=200)
    module: str | None = Field(None, min_length=1, max_length=50)
    priority: str | None = Field(None, pattern="^P[0-3]$")
    case_type: str | None = None
    source: str | None = None
    precondition: str | None = None
    steps: str | None = None
    expected_result: str | None = Field(None, min_length=1)
    status: str | None = None
    tags: str | None = None
    module_code: str | None = None
    case_code: str | None = None


class TestCaseResponse(BaseModel):
    """用例响应：附带回显的项目编码/名称"""
    id: int
    project_id: int
    project_code: str | None = None
    project_name: str | None = None
    title: str
    module: str
    priority: str
    case_type: str
    source: str | None = None
    precondition: str | None = None
    steps: str | None = None
    expected_result: str
    status: str
    tags: str | None = None
    module_code: str | None = None
    case_code: str | None = None
    created_at: datetime
    updated_at: datetime
