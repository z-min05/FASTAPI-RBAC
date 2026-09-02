"""LLM provider factory — 按配置动态创建不同供应商的 LLM 实例。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger("agent.llm_factory")

_LLM_REGISTRY: dict[str, type[BaseChatModel]] = {}


def register_llm_provider(name: str):
    def decorator(cls: type[BaseChatModel]):
        _LLM_REGISTRY[name.lower()] = cls
        return cls
    return decorator


def _populate_builtin_providers() -> None:
    try:
        from langchain_openai import ChatOpenAI

        @register_llm_provider("openai")
        class _OpenAI(ChatOpenAI):  # type: ignore[no-redef]
            ...
    except ImportError:
        logger.debug("langchain-openai not installed, skipping")

    try:
        from langchain_openai import AzureChatOpenAI

        @register_llm_provider("azure")
        class _Azure(AzureChatOpenAI):  # type: ignore[no-redef]
            ...
    except ImportError:
        logger.debug("Azure OpenAI provider not available")

    try:
        from langchain_anthropic import ChatAnthropic

        @register_llm_provider("anthropic")
        class _Anthropic(ChatAnthropic):  # type: ignore[no-redef]
            ...
    except ImportError:
        logger.debug("langchain-anthropic not installed, skipping")

    try:
        from langchain_ollama import ChatOllama

        @register_llm_provider("ollama")
        class _Ollama(ChatOllama):  # type: ignore[no-redef]
            ...
    except ImportError:
        logger.debug("langchain-ollama not installed, skipping")


_populate_builtin_providers()

# 需要 base_url / api_key 的供应商
_PROVIDERS_WITH_BASE_URL = {"openai"}
_PROVIDERS_WITH_API_KEY = {"openai", "azure", "anthropic"}

# 供应商参数名差异映射（如 ollama 的 max_tokens -> num_predict）
_SPECIAL_PARAMS = {
    "ollama": {"max_tokens": "num_predict"},
}

_TIMEOUT_PARAMS = {"ollama": "request_timeout"}


class LLMFactory:
    """LLM 实例工厂。"""

    @staticmethod
    def create(
        provider: str,
        *,
        model: str = "gpt-4o",
        max_retries: int = 2,
        timeout: float | None = None,
        base_url: str = "",
        api_key: str = "",
        **kwargs: Any,
    ) -> BaseChatModel:
        key = provider.lower()
        if key not in _LLM_REGISTRY:
            available = ", ".join(sorted(_LLM_REGISTRY)) or "(none)"
            raise ValueError(f"未知 LLM 供应商 '{provider}'。已注册: {available}")

        cls = _LLM_REGISTRY[key]
        kwargs["max_retries"] = max_retries
        kwargs.setdefault("temperature", 0.3)

        # OpenAI 兼容服务：必须显式开启增量流式，否则 graph 的 messages 流模式
        # 每次模型调用只产出一个整块 chunk（文本一次性全部出现、不像流式）；
        # stream_usage 让末尾 chunk 携带 usage，供流式 Token 结算使用。
        if key in {"openai", "azure"}:
            kwargs.setdefault("streaming", True)
            kwargs.setdefault("stream_usage", True)

        # 供应商参数名差异映射（如 ollama 的 max_tokens -> num_predict）
        mapping = _SPECIAL_PARAMS.get(key, {})
        for src, dst in mapping.items():
            if src in kwargs:
                kwargs[dst] = kwargs.pop(src)

        # 超时参数名差异
        if timeout is not None and timeout > 0:
            timeout_param = _TIMEOUT_PARAMS.get(key, "timeout")
            kwargs[timeout_param] = timeout

        # OpenAI 兼容服务的 base_url
        if key in _PROVIDERS_WITH_BASE_URL and base_url:
            kwargs["base_url"] = base_url

        # API Key（ollama 等本地服务不需要）
        if key in _PROVIDERS_WITH_API_KEY and api_key:
            kwargs["api_key"] = api_key

        logger.info(
            "创建 LLM: provider=%s, model=%s, max_retries=%d, timeout=%s",
            provider, model, max_retries, timeout,
        )
        return cls(model=model, **kwargs)  # type: ignore[call-arg]

    @staticmethod
    def from_string(model_string: str, **kwargs: Any) -> BaseChatModel:
        if ":" in model_string:
            provider, model = model_string.split(":", 1)
        else:
            provider, model = "openai", model_string
        return LLMFactory.create(provider=provider, model=model, **kwargs)
