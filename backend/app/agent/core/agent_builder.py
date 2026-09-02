"""Agent 构建器 —— 封装 LangChain 1.x 统一的 create_agent API。

提供：
- 工具动态注入
- 中间件管线配置
- 记忆/Checkpointer 配置
- 结构化输出支持

设计为 Builder 模式，支持链式调用。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

logger = logging.getLogger("agent.builder")


class AgentBuilder:
    """Agent 构建器。"""

    def __init__(self) -> None:
        self._llm: BaseChatModel | str | None = None
        self._tools: list[BaseTool] = []
        self._system_prompt: str | None = None
        self._middlewares: list[Any] = []
        self._checkpointer: Any = None
        self._response_format: Any = None
        self._config: dict[str, Any] = {}

    def with_llm(self, llm: BaseChatModel | str) -> "AgentBuilder":
        """设置 LLM。接受模型实例或 'provider:model' 字符串。"""
        self._llm = llm
        return self

    def with_tools(self, tools: Sequence[BaseTool]) -> "AgentBuilder":
        self._tools = list(tools)
        return self

    def with_system_prompt(self, prompt: str) -> "AgentBuilder":
        self._system_prompt = prompt
        return self

    def with_middleware(self, *middlewares: Any) -> "AgentBuilder":
        self._middlewares.extend(middlewares)
        return self

    def with_checkpointer(self, checkpointer: Any) -> "AgentBuilder":
        self._checkpointer = checkpointer
        return self

    def with_memory_checkpointer(self) -> "AgentBuilder":
        """使用内存 checkpointer（开发/测试用）。"""
        self._checkpointer = InMemorySaver()
        return self

    def with_response_format(self, schema: Any) -> "AgentBuilder":
        self._response_format = schema
        return self

    def with_config(self, **kwargs: Any) -> "AgentBuilder":
        self._config.update(kwargs)
        return self

    def build(self) -> Any:
        """构建并返回 LangGraph 编译后的 Agent 图。"""
        if self._llm is None:
            raise ValueError("必须调用 with_llm() 设置 LLM")

        kwargs: dict[str, Any] = {"model": self._llm}
        if self._tools:
            kwargs["tools"] = self._tools
        if self._system_prompt is not None:
            kwargs["system_prompt"] = self._system_prompt
        if self._middlewares:
            kwargs["middleware"] = self._middlewares
        if self._checkpointer is not None:
            kwargs["checkpointer"] = self._checkpointer
        if self._response_format is not None:
            kwargs["response_format"] = self._response_format
        kwargs.update(self._config)

        logger.info(
            "构建 Agent: model=%s, tools=%s, middleware=%s",
            kwargs.get("model"),
            [t.name for t in self._tools] if self._tools else [],
            [type(m).__name__ for m in self._middlewares],
        )
        return create_agent(**kwargs)
