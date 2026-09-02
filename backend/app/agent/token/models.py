"""Token 消耗数据模型。"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TokenRecord(BaseModel):
    """单次 LLM 调用的 token 消耗记录。"""

    timestamp: datetime = Field(default_factory=datetime.now)
    model: str = ""
    step: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls: list[str] = Field(default_factory=list)
