"""统一中间件 —— 日志 + Token 采集 + 消息清洗（logger 落库版，无 rich）。"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable

from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

from app.agent.token.ledger import TokenLedger
from app.agent.token.models import TokenRecord

logger = logging.getLogger("agent.middleware")


def _sanitize_messages(messages: list) -> list:
    """清洗消息列表，确保每条消息都有合法的 content 或 tool_calls。

    某些 OpenAI 兼容 API 要求每条 message 必须有 content 或 tool_calls，
    但 LangChain 在 Agent 调用工具时可能生成 content=None 的 AIMessage。
    """
    for msg in messages:
        # AIMessage: 如果有 tool_calls 但 content 为空，补一个空字符串
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            if not msg.content:
                msg.content = ""
        # AIMessage: 如果 content 是 None，补空字符串
        if hasattr(msg, "content") and msg.content is None:
            msg.content = ""
        # ToolMessage: 如果 content 是 dict/list，序列化为 JSON 字符串
        if hasattr(msg, "type") and msg.type == "tool":
            if isinstance(msg.content, (dict, list)):
                msg.content = json.dumps(msg.content, ensure_ascii=False)
            elif not msg.content:
                msg.content = ""
    return messages


def create_agent_middleware(ledger: TokenLedger | None = None):
    """工厂函数：创建统一中间件（日志 + Token 采集 + 消息清洗）。

    返回的中间件函数附带 reset_steps() 方法，供外部在每轮对话
    开始前将步骤号归零，保证每次提问都从 Step 1 开始。
    """
    # request.state 每次模型调用都会新建，无法跨调用计数；
    # 用闭包变量计数，并提供 reset_steps() 在每轮对话开始时归零。
    _step_state = {"n": 0}

    def _reset_steps() -> None:
        _step_state["n"] = 0

    @wrap_model_call
    def AgentMiddleware(
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        _step_state["n"] += 1
        step = _step_state["n"]

        tool_names = [t.name for t in request.tools] if request.tools else []

        model_name = "unknown"
        bound = getattr(request, "model", None)
        if bound is not None:
            model_name = (
                getattr(bound, "model", None)
                or getattr(bound, "model_name", None)
                or type(bound).__name__
            )

        logger.info("[Step %d] 开始调用 LLM, model=%s, tools=%s", step, model_name, tool_names)

        # 清洗消息，防止 API 500 错误
        try:
            messages = getattr(request, "messages", None)
            if messages:
                _sanitize_messages(messages)
        except Exception as exc:
            logger.debug("消息清洗异常（非致命）: %s", exc)

        # 调用 LLM
        start = time.perf_counter()
        response = handler(request)
        elapsed = time.perf_counter() - start

        logger.info("[Step %d] 调用完成, 耗时 %.2fs", step, elapsed)

        # Token 采集
        if ledger is not None:
            try:
                result = response.result
                result_msgs = result if isinstance(result, list) else [result]

                input_tokens = output_tokens = total_tokens = 0

                for msg in reversed(result_msgs):
                    um = getattr(msg, "usage_metadata", None)
                    if um and isinstance(um, dict) and um.get("total_tokens", 0):
                        input_tokens = um.get("input_tokens", 0) or 0
                        output_tokens = um.get("output_tokens", 0) or 0
                        total_tokens = um.get("total_tokens", 0) or 0
                        break

                    rm = getattr(msg, "response_metadata", None) or {}
                    tu = rm.get("token_usage", {}) if isinstance(rm, dict) else {}
                    if tu and tu.get("total_tokens", 0):
                        input_tokens = tu.get("prompt_tokens", 0) or 0
                        output_tokens = tu.get("completion_tokens", 0) or 0
                        total_tokens = tu.get("total_tokens", 0) or 0
                        break

                if total_tokens > 0:
                    record = TokenRecord(
                        model=str(model_name),
                        step=step,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        tool_calls=tool_names,
                    )
                    ledger.add(record)
                    logger.info(
                        "[Step %d] Token: 输入=%d 输出=%d 合计=%d",
                        step, input_tokens, output_tokens, total_tokens,
                    )
                else:
                    logger.warning("[Step %d] 未提取到 token", step)

            except Exception as exc:
                logger.warning("[Step %d] Token 采集异常: %s", step, exc)

        return response

    # 供外部在每轮对话开始前重置步骤号
    AgentMiddleware.reset_steps = _reset_steps  # type: ignore[attr-defined]
    return AgentMiddleware
