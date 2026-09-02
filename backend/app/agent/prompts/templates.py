"""系统提示词：V2 直接使用用户输入的文字提示词，不做模板映射。"""

from __future__ import annotations

from typing import Optional


def resolve_system_prompt(prompt: Optional[str]) -> Optional[str]:
    """返回用户输入的系统提示词；空串/空白视为未设置（交给 LangChain 内部默认）。"""
    text = (prompt or "").strip()
    return text if text else None
