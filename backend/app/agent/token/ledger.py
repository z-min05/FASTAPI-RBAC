"""Token 消耗账本（进程内，每轮对话结束后由 service 落库）。"""

from __future__ import annotations

import threading

from app.agent.token.models import TokenRecord


class TokenLedger:
    """线程安全的 token 消耗账本。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[TokenRecord] = []

    @property
    def records(self) -> list[TokenRecord]:
        with self._lock:
            return list(self._records)

    def add(self, record: TokenRecord) -> None:
        with self._lock:
            self._records.append(record)

    def drain(self) -> list[TokenRecord]:
        """取出并清空全部记录（每轮对话结束由 service 落库后调用）。"""
        with self._lock:
            records = self._records
            self._records = []
            return records

    def reset(self) -> None:
        with self._lock:
            self._records.clear()

    @property
    def total_input(self) -> int:
        return sum(r.input_tokens for r in self._records)

    @property
    def total_output(self) -> int:
        return sum(r.output_tokens for r in self._records)

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self._records)

    @property
    def call_count(self) -> int:
        return len(self._records)
