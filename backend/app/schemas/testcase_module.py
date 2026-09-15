from datetime import datetime

from pydantic import BaseModel, Field


class TestCaseModuleCreate(BaseModel):
    """新建模块节点。新建时必然是末级，故 code 只校验字符集，不强制 test_ 前缀。"""

    project_id: int = Field(..., description="所属项目")
    parent_id: int | None = Field(None, description="上级模块，空表示顶级")
    name: str = Field(..., min_length=1, max_length=50, description="模块名称（展示用）")
    code: str = Field(..., min_length=1, max_length=100, description="目录名，或末级模块的 pytest 文件名")
    description: str | None = Field(None, max_length=500)
    sort: int = 0


class TestCaseModuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    code: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    sort: int | None = None
    parent_id: int | None = Field(None, description="上级模块，显式传 null 表示移到顶级")


class TestCaseModuleResponse(BaseModel):
    id: int
    project_id: int
    parent_id: int | None = None
    name: str
    code: str
    description: str | None = None
    sort: int
    is_leaf: bool = True
    module_path: str = ""
    case_count: int = 0
    total_case_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCaseModuleTreeNode(TestCaseModuleResponse):
    """树节点：附带子节点"""

    children: list["TestCaseModuleTreeNode"] = []


TestCaseModuleTreeNode.model_rebuild()
