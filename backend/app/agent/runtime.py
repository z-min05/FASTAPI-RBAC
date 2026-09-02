"""Agent 运行时 V2：多 Agent 实例缓存 + run_round 串行执行。

- LLM/工具/提示词均来自服务层传入的 spec（由 DB 中 Agent + LLM 配置组装）；
- 按 agent_id 做进程内实例缓存（LRU，上限 _CACHE_MAX），配置 hash 变化自动重建；
- run_round：全局 asyncio 锁内完成 reset -> invoke(线程池+超时) -> drain，
  保证 token 账本（进程级 ledger）与 PG Checkpointer 连接均单飞安全；
- invoke 为同步阻塞调用，必须经 asyncio.to_thread 执行。
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import OrderedDict
from typing import Any

from langchain_core.messages import AIMessageChunk, ToolMessageChunk

from app.agent.config import get_agent_config
from app.agent.core.agent_builder import AgentBuilder
from app.agent.core.llm_factory import LLMFactory
from app.agent.memory.checkpointer import create_checkpointer, get_postgres_saver
from app.agent.middleware.agent_middleware import create_agent_middleware
from app.agent.prompts.templates import resolve_system_prompt
from app.agent.token.ledger import TokenLedger
from app.agent.token.models import TokenRecord
from app.agent.tools.registry import ToolRegistry
from app.utils.logger import logger

# 进程级 Token 账本（每一轮 run_round 内重置并 drain）
ledger = TokenLedger()

# 全局工具注册表（静态，与具体 Agent 无关；Agent 按自身 tools 勾选过滤）
_registry = ToolRegistry()
_registry.autodiscover("app.agent.tools.builtin")

_CACHE_MAX = 32
_cache: "OrderedDict[int, _Instance]" = OrderedDict()
_build_lock = threading.Lock()
_round_lock = asyncio.Lock()


class AgentInvokeError(RuntimeError):
    """一轮 Agent 推理失败（含超时）。携带已产生的 token 记录供审计落库。"""

    def __init__(self, message: str, records: list | None = None, timed_out: bool = False):
        super().__init__(message)
        self.records = records or []
        self.timed_out = timed_out


class _Instance:
    __slots__ = ("agent_id", "hash", "graph", "middleware", "last_used")

    def __init__(self, agent_id: int, cfg_hash: str, graph: Any, middleware: Any):
        self.agent_id = agent_id
        self.hash = cfg_hash
        self.graph = graph
        self.middleware = middleware
        self.last_used = time.monotonic()


def list_tool_names() -> list[str]:
    """注册表内全部可用工具名（供 Agent 管理页勾选 + 服务层白名单校验）。"""
    return _registry.list_names()


def available_tools() -> list[dict]:
    """全部可用工具（含描述，供前端能力展示）。"""
    return [
        {"name": t.name, "description": getattr(t, "description", "")}
        for t in _registry.get_all()
    ]


def _build_instance(spec: dict) -> _Instance:
    """按 spec（LLM 配置 + 提示词 + 工具勾选）构建一个 LangGraph Agent 实例。"""
    llm_cfg = spec.get("llm") or {}
    tools = _registry.get_enabled(list(spec.get("tools") or []))
    middleware = create_agent_middleware(ledger)

    llm = LLMFactory.create(
        llm_cfg.get("provider") or "openai",
        model=llm_cfg.get("model"),
        base_url=llm_cfg.get("base_url"),
        api_key=llm_cfg.get("api_key"),
        temperature=llm_cfg.get("temperature", 0.3),
        max_tokens=llm_cfg.get("max_tokens", 2048),
        timeout=llm_cfg.get("timeout", 60),
    )

    builder = (
        AgentBuilder()
        .with_llm(llm)
        .with_tools(tools)
        .with_middleware(middleware)
        .with_checkpointer(create_checkpointer("postgres"))
    )
    prompt = resolve_system_prompt(spec.get("system_prompt"))
    if prompt:
        builder.with_system_prompt(prompt)

    graph = builder.build()
    agent_id = int(spec.get("agent_id") or 0)
    logger.info("Agent 实例构建完成: agent_id=%s tools=%s", agent_id, [t.name for t in tools])
    return _Instance(agent_id, spec.get("hash") or "", graph, middleware)


def _get_or_build(spec: dict) -> _Instance:
    """实例缓存：命中(hash 相同)则复用；未命中/配置变更则重建并淘汰最旧。"""
    agent_id = int(spec.get("agent_id") or 0)
    cfg_hash = spec.get("hash") or ""
    with _build_lock:
        inst = _cache.get(agent_id)
        if inst is not None and inst.hash == cfg_hash:
            inst.last_used = time.monotonic()
            _cache.move_to_end(agent_id)
            return inst
        inst = _build_instance(spec)
        _cache[agent_id] = inst
        _cache.move_to_end(agent_id)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
        return inst


async def run_round(spec: dict, input_data: dict, config: dict) -> tuple[Any, list]:
    """执行一轮对话（串行）：reset -> invoke(线程池+超时) -> drain。

    成功返回 (result, token_records)；失败抛 AgentInvokeError（records 已捕获）。
    """
    inst = _get_or_build(spec)
    timeout = get_agent_config().invoke_timeout

    async with _round_lock:
        # 每轮重置步骤号与账本（全局串行保证账本归属当前轮）
        if inst.middleware is not None:
            try:
                inst.middleware.reset_steps()
            except Exception:
                pass
        ledger.reset()

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(inst.graph.invoke, input_data, config),
                timeout=timeout,
            )
            records = ledger.drain()
            return result, records
        except Exception as exc:
            records = ledger.drain()
            if isinstance(exc, asyncio.TimeoutError):
                raise AgentInvokeError("Agent 推理超时", records=records, timed_out=True) from exc
            logger.warning("Agent invoke 失败: %s", exc)
            raise AgentInvokeError(f"Agent 推理失败: {exc}", records=records) from exc


async def clear_memory(thread_id: str) -> None:
    """删除某线程的引擎记忆（PG checkpoint 状态），会话删除时调用。

    与 run_round 共用 _round_lock：共享的同步 PG 连接单飞，避免与
    正在进行的推理并发占用；清理失败仅告警，不阻塞业务删除。
    """
    async with _round_lock:
        try:
            saver = get_postgres_saver()
            await asyncio.to_thread(saver.delete_thread, thread_id)
            logger.info("已清理线程记忆 thread_id=%s", thread_id)
        except Exception:
            logger.warning("清理线程记忆失败 thread_id=%s", thread_id, exc_info=True)


# ==================== 流式执行（SSE） ====================


def _chunk_text(content: Any) -> str:
    """从消息 chunk 中提取纯文本片段（兼容 str / 多模态块列表）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(str(block.get("text") or ""))
    return "".join(parts)


def _parse_tool_args(raw: str) -> Any:
    """尽力解析工具参数 JSON，解析失败时返回原始字符串。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _try_parse_args(raw: str) -> Any:
    """工具参数流式片段是否已凑成完整 JSON：是则返回解析结果，否则返回 None。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _stream_events(
    spec: dict,
    inst: _Instance,
    input_data: dict,
    config: dict,
    emit,
    stop: threading.Event,
) -> dict:
    """在 worker 线程内消费 graph.stream(messages)，通过 emit 回调推送事件。

    返回汇总：{"ok": bool, "error": str|None, "reply": str, "derived": [TokenRecord, ...]}
    """
    model_name = (spec.get("llm") or {}).get("model") or "unknown"
    derived: list[TokenRecord] = []
    reply: str = ""
    error: str | None = None

    # 当前模型消息的积累（id 变化 / 工具结果到达时结算）
    ai = {"id": "", "text": "", "usage": None, "tools": {}}  # tools: call_id -> {name,args,emitted}
    # 当前工具结果输出（以 ToolMessage 为单位收集，下一条消息/结束时结算）
    tool_out = {"id": "", "call_id": "", "parts": []}
    emitted_index: dict[str, int] = {}
    emitted_order: list[str] = []
    resulted: set[str] = set()
    tool_seq = {"n": -1}
    step_no = {"n": 0}

    def _emit_tool(call_id: str, entry: dict, args: Any) -> None:
        tool_seq["n"] += 1
        emitted_index[call_id] = tool_seq["n"]
        emitted_order.append(call_id)
        emit(
            {
                "type": "tool",
                "index": tool_seq["n"],
                "name": entry.get("name") or "未知工具",
                "args": args,
                "call_id": call_id,
            }
        )
        entry["emitted"] = True

    def _usage_record(usage: Any, tool_names: list[str]) -> None:
        if not usage or not usage.get("total_tokens"):
            return
        step_no["n"] += 1
        derived.append(
            TokenRecord(
                model=model_name,
                step=step_no["n"],
                input_tokens=usage.get("input_tokens") or 0,
                output_tokens=usage.get("output_tokens") or 0,
                total_tokens=usage.get("total_tokens") or 0,
                tool_calls=tool_names,
            )
        )

    def _flush_ai() -> None:
        nonlocal reply
        if not ai["id"]:
            return
        tools = ai["tools"]
        _usage_record(ai["usage"], [t["name"] for t in tools.values()])
        if tools:
            # 补齐流式过程中未及下发的工具调用（参数未收敛为 JSON 等兜底）
            for call_id, t in tools.items():
                if t["emitted"]:
                    continue
                _emit_tool(call_id, t, _parse_tool_args(t["args"]))
        elif ai["text"]:
            # 无工具调用且含文本 → 本轮最终回复
            reply = ai["text"]
        ai["id"] = ""
        ai["text"] = ""
        ai["usage"] = None
        ai["tools"] = {}

    def _flush_tool_out() -> None:
        if not tool_out["id"]:
            return
        output = "".join(tool_out["parts"])
        if len(output) > 2000:
            output = output[:2000] + "…（输出过长已截断）"
        call_id = tool_out["call_id"] or ""
        index = emitted_index.get(call_id, -1)
        if index < 0:
            # 兜底：部分提供商的 ToolMessage 不带 tool_call_id，
            # 按“最早仍未返回结果”的工具调用顺序匹配
            for cid in emitted_order:
                if cid in resulted:
                    continue
                index = emitted_index.get(cid, -1)
                call_id = cid
                break
        if index >= 0 and call_id:
            resulted.add(call_id)
        emit(
            {
                "type": "tool_result",
                "index": index,
                "call_id": call_id,
                "output": output,
            }
        )
        tool_out["id"] = ""
        tool_out["call_id"] = ""
        tool_out["parts"] = []

    def _collect_ai(chunk) -> None:
        """积累文本 / usage / 工具调用，参数一凑齐就尽早下发 tool 事件。"""
        text = _chunk_text(chunk.content)
        if text:
            ai["text"] += text
            emit({"type": "text", "content": text})
        if getattr(chunk, "usage_metadata", None):
            ai["usage"] = chunk.usage_metadata

        raw_calls = getattr(chunk, "tool_call_chunks", None) or []
        if raw_calls:
            for tc in raw_calls:
                call_id = tc.get("id") or ""
                if not call_id:
                    continue
                entry = ai["tools"].setdefault(
                    call_id, {"name": "", "args": "", "emitted": False}
                )
                if tc.get("name"):
                    entry["name"] = tc["name"]
                if tc.get("args"):
                    entry["args"] += tc["args"]
        else:
            # 非流式/聚合消息：tool_calls 已是完整结构
            for tc in getattr(chunk, "tool_calls", None) or []:
                call_id = tc.get("id") or ""
                if not call_id:
                    continue
                entry = ai["tools"].setdefault(
                    call_id, {"name": "", "args": "", "emitted": False}
                )
                if tc.get("name"):
                    entry["name"] = tc["name"]
                args = tc.get("args")
                if isinstance(args, dict):
                    entry["args"] = json.dumps(args, ensure_ascii=False)
                elif args is not None:
                    entry["args"] = str(args)

        # 模型回复过程中参数流即收敛为完整 JSON → 立刻提示“正在调用工具”，
        # 而不是等工具结果返回后才让前端看到调用
        for call_id, entry in ai["tools"].items():
            if entry["emitted"] or not entry.get("name"):
                continue
            args = _try_parse_args(entry["args"])
            if args is not None:
                _emit_tool(call_id, entry, args)

    def _is_ai_chunk(chunk) -> bool:
        return isinstance(chunk, AIMessageChunk) or getattr(chunk, "type", None) == "ai"

    def _is_tool_msg(chunk) -> bool:
        return isinstance(chunk, ToolMessageChunk) or getattr(chunk, "type", None) == "tool"

    try:
        for chunk, _meta in inst.graph.stream(input_data, config, stream_mode="messages"):
            if stop.is_set():
                break
            if _is_ai_chunk(chunk):
                # 新一轮 model 调用开始：先结算上一条模型消息，再补发残留的工具结果
                chunk_id = getattr(chunk, "id", None) or ""
                if ai["id"] and chunk_id and chunk_id != ai["id"]:
                    _flush_ai()
                _flush_tool_out()
                if not ai["id"]:
                    ai["id"] = chunk_id or "__model__"
                _collect_ai(chunk)
            elif _is_tool_msg(chunk):
                # 工具结果到达：结算上一条模型消息（补发工具事件/usage），再收集输出
                _flush_ai()
                _flush_tool_out()
                tool_out["id"] = getattr(chunk, "id", None) or (
                    getattr(chunk, "tool_call_id", None) or "__tool__"
                )
                tool_out["call_id"] = getattr(chunk, "tool_call_id", None) or ""
                tool_out["parts"].append(_chunk_text(chunk.content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agent 流式执行异常: %s", exc)
        error = str(exc)
    finally:
        _flush_tool_out()
        _flush_ai()

    return {"ok": error is None, "error": error, "reply": reply, "derived": derived}


async def stream_round(spec: dict, input_data: dict, config: dict) -> Any:
    """流式执行一轮对话，产出 SSE 事件。

    事件格式：
      {"type": "text", "content": str}            回复文本增量
      {"type": "tool", "index": int, "name": str, "args": obj|str, "call_id": str}
      {"type": "tool_result", "index": int, "output": str, "call_id": str}
      {"type": "final", "reply": str, "records": [TokenRecord...]}  收尾（含结算记录）

    失败（含超时）抛出 AgentInvokeError（records 为已采集的 Token 记录）。
    与 run_round 共用 _round_lock，保证 PG 连接与账本单飞。
    """
    inst = _get_or_build(spec)
    timeout = get_agent_config().invoke_timeout

    async with _round_lock:
        if inst.middleware is not None:
            try:
                inst.middleware.reset_steps()
            except Exception:
                pass
        ledger.reset()

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stop = threading.Event()
        summary: dict = {}

        def emit(ev: Any) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ev)

        def _worker() -> None:
            try:
                summary.update(_stream_events(spec, inst, input_data, config, emit, stop))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Agent 流式 worker 异常: %s", exc)
                summary["ok"] = False
                summary["error"] = str(exc)
            emit(None)  # 哨兵

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        try:
            deadline = time.monotonic() + timeout
            while True:
                remain = deadline - time.monotonic()
                if remain <= 0:
                    raise AgentInvokeError("Agent 推理超时", records=ledger.drain(), timed_out=True)
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=min(remain, 5.0))
                except asyncio.TimeoutError:
                    continue
                if ev is None:
                    break
                yield ev
        finally:
            stop.set()
            ledger.reset()

        # Token 结算：流式下中间件聚合拿不到 usage 时回退 chunk usage 推导
        ledger_recs = ledger.drain()
        ledger.reset()
        records = ledger_recs or summary.get("derived") or []
        if not summary.get("ok", True):
            raise AgentInvokeError(summary.get("error") or "Agent 推理失败", records=records)
        yield {"type": "final", "reply": summary.get("reply") or "", "records": records}
