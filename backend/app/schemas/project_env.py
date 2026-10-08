from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EnvLine(BaseModel):
    """环境文件的单行解析结果（保留原始行，供表格/原文双视图互转）"""
    no: int = Field(..., description="行号，从 1 开始")
    type: Literal["comment", "blank", "kv", "raw"]
    raw: str = Field(..., description="原始整行内容")
    key: str | None = None
    value: str | None = None
    sensitive: bool = Field(False, description="键名疑似敏感（密码/token 等），前端默认打码显示")


class EnvListItem(BaseModel):
    name: str
    remark: str | None = None
    created_by: int | None = None
    key_count: int = 0
    size: int = 0
    updated_at: datetime | None = None
    is_active: bool = Field(False, description="是否当前生效环境")
    external: bool = Field(False, description="平台外手工放入的文件（无备注记录）")


class EnvListResponse(BaseModel):
    project_root: str
    has_active_env_file: bool
    active_env: str | None = None
    drifted: bool = Field(False, description=".env 与所有环境快照均不一致（有未归档修改）")
    duplicated: list[str] = Field(default_factory=list, description="内容完全相同的环境名")
    items: list[EnvListItem] = Field(default_factory=list)


class EnvDetailResponse(BaseModel):
    name: str | None = None
    exists: bool = True
    content: str = ""
    lines: list[EnvLine] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_active: bool = False
    remark: str | None = None


class EnvSaveRequest(BaseModel):
    content: str = Field(..., description="环境文件完整内容（保存时会统一换行为 LF）")
    remark: str | None = Field(None, max_length=200)


class EnvSaveResponse(BaseModel):
    name: str
    is_active: bool = False
    backup: str | None = None
    warnings: list[str] = Field(default_factory=list)


class EnvCreateRequest(BaseModel):
    name: str = Field(..., max_length=64, description="环境名（字母数字下划线中划线）")
    source: Literal["active", "empty", "content"] = Field(
        "active", description="active=复制当前 .env / empty=空白 / content=使用 content 字段"
    )
    content: str | None = None
    remark: str | None = Field(None, max_length=200)


class EnvUploadRequest(BaseModel):
    filename: str = Field(..., max_length=200, description="上传的原始文件名，用于推导环境名")
    content: str
    remark: str | None = Field(None, max_length=200)


class EnvRenameRequest(BaseModel):
    new_name: str = Field(..., max_length=64)


class EnvApplyResponse(BaseModel):
    active_env: str
    backup: str | None = None


class EnvDiffItem(BaseModel):
    key: str
    left: str | None = None
    right: str | None = None


class EnvDiffResponse(BaseModel):
    left: str
    right: str
    added: list[EnvDiffItem] = Field(default_factory=list)
    removed: list[EnvDiffItem] = Field(default_factory=list)
    changed: list[EnvDiffItem] = Field(default_factory=list)
