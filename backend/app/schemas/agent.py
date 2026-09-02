from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ==================== LLM 配置（超管维护） ====================


class LlmBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., max_length=30)
    model: str = Field(..., min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, max_length=255)
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=1)
    timeout: int = Field(60, ge=1)
    enabled: bool = True
    remark: Optional[str] = Field(None, max_length=500)


class LlmCreate(LlmBase):
    api_key: Optional[str] = Field(None, max_length=2000)


class LlmUpdate(BaseModel):
    """编辑 LLM：api_key 为空表示不修改（不回显）。"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider: Optional[str] = Field(None, max_length=30)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, max_length=255)
    api_key: Optional[str] = Field(None, max_length=2000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    timeout: Optional[int] = Field(None, ge=1)
    enabled: Optional[bool] = None
    remark: Optional[str] = Field(None, max_length=500)


class LlmResponse(BaseModel):
    """对外返回：api_key 始终为掩码。"""
    id: int
    name: str
    provider: str
    model: str
    base_url: Optional[str]
    api_key_mask: str
    temperature: float
    max_tokens: int
    timeout: int
    enabled: bool
    remark: Optional[str]
    created_at: datetime
    updated_at: datetime


# ==================== Agent 定义（用户自建） ====================


class AgentDefBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    system_prompt: str = Field("", max_length=20000, description="用户直接输入的文字提示词，可为空")
    tools: list[str] = Field(default_factory=list, description="勾选工具名，默认不选")


class AgentDefCreate(AgentDefBase):
    llm_id: int = Field(..., gt=0)


class AgentDefUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    llm_id: Optional[int] = Field(None, gt=0)
    system_prompt: Optional[str] = Field(None, max_length=20000)
    tools: Optional[list[str]] = None
    enabled: Optional[bool] = None


class AgentDefResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    llm_id: int
    llm_name: Optional[str] = None
    llm_model: Optional[str] = None
    system_prompt: str
    tools: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== 会话 ====================


class ConversationCreate(BaseModel):
    agent_id: int = Field(..., gt=0, description="选用用户自己的 Agent")
    title: Optional[str] = Field(None, max_length=200)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = Field(None, pattern="^(active|archived)$")


class ConversationResponse(BaseModel):
    id: int
    title: str
    agent_id: Optional[int]
    agent_name: Optional[str] = None
    model: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageSend(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: Optional[str]
    token_total: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenStatItem(BaseModel):
    """单条 token 记录（明细）"""
    id: int
    conversation_id: Optional[int]
    model: str
    step: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenStatSummary(BaseModel):
    """我的 Token 汇总"""
    call_count: int = 0
    total_input: int = 0
    total_output: int = 0
    total_tokens: int = 0
    by_model: list[dict] = Field(default_factory=list)
