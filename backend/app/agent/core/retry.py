"""LLM 请求退避调度：把 openai 兼容客户端的重试等待窗口拉长。

openai SDK 默认退避是 `0.5s * 2^n` 且单次上限 8s——遇到按分钟计的 TPM/RPM 限流
（HTTP 429，如 `inference exceeds tpm/rpm limit`）时窗口过短，重试往往在同一分钟内
再次被拒，整轮对话直接失败。

这里在**实例级**替换客户端的 `_calculate_retry_timeout`，改为 `initial * 2^n`
（单次等待上限 max_delay），服务端给了 `Retry-After` 时优先遵循。只改「等多久」，
「重试几次」仍由 `max_retries` 控制；超过次数后按轮失败处理（由上层落库并提示）。

注意：只影响重试间隔，不会重试已经吐字的流式响应——SDK 只在「请求建立阶段」
（429/5xx/连接错误）触发重试，不会重放已开始输出的流，因此不会产生重复文本。
"""

from __future__ import annotations

import random
import types
from typing import Any, Callable

from app.utils.logger import logger

# 与 openai SDK 保持一致：Retry-After 超过 120s 视为不可等待，退回自身调度
_MAX_RETRY_AFTER = 120.0


def _build_calculator(initial: float, max_delay: float) -> Callable[..., float]:
    """构造替代 `_calculate_retry_timeout` 的调度函数（签名与 SDK 保持一致）。"""

    def _calculate_retry_timeout(
        self: Any, remaining_retries: int, options: Any, response_headers: Any = None
    ) -> float:
        # 1) 服务端明确给了 Retry-After → 优先遵循
        try:
            retry_after = self._parse_retry_after_header(response_headers)
        except Exception:
            retry_after = None
        if retry_after is not None and 0 < retry_after <= _MAX_RETRY_AFTER:
            return retry_after

        # 2) 否则按第几次重试指数退避：initial、2*initial、4*initial…（单次封顶）
        max_retries = getattr(self, "max_retries", None) or 0
        try:
            max_retries = options.get_max_retries(max_retries)
        except Exception:
            pass
        attempt = max(0, int(max_retries or 0) - int(remaining_retries or 0))
        delay = min(initial * (2**attempt), max_delay)
        # 抖动 ±25%，避免多进程同时重试再次撞上限流
        return delay * (1 - 0.25 * random.random())

    return _calculate_retry_timeout


def apply_backoff(client: Any, *, initial: float, max_delay: float) -> None:
    """把客户端的重试等待调度替换为自定义退避。

    替换失败（SDK 内部结构变化）时仅告警并沿用默认调度，不影响正常调用。
    """
    if client is None or initial <= 0:
        return
    try:
        client._calculate_retry_timeout = types.MethodType(
            _build_calculator(initial, max_delay), client
        )
    except Exception:
        logger.warning("替换 LLM 重试退避调度失败，沿用 SDK 默认退避", exc_info=True)
