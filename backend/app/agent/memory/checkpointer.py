"""PostgreSQL Checkpointer：会话记忆（多轮状态）持久化到平台数据库。

V2 固定使用 Postgres 后端：
- 复用 DATABASE_URL，仅将异步驱动转换为 psycopg 同步驱动（agent.invoke 在线程池中同步执行）；
- 进程级共享一个 saver 实例（LangGraph 建表 langgraph_checkpoint* 由 setup() 完成）；
- 所有 Agent 实例共用该 saver，配合 runtime 全局串行调用保证连接安全。
"""

from __future__ import annotations

import threading
from contextlib import ExitStack
from typing import Any

from sqlalchemy.engine import make_url

from app.config import settings
from app.utils.logger import logger

_saver: Any = None
_saver_stack: ExitStack | None = None
_saver_lock = threading.Lock()


def _sync_db_url() -> str:
    """将 DATABASE_URL 转成 psycopg 可用的同步连接串。"""
    url = make_url(settings.DATABASE_URL)
    sync_url = url.set(drivername="postgresql")
    return sync_url.render_as_string(hide_password=False)


def get_postgres_saver() -> Any:
    """获取进程级共享的 PostgresSaver（首次调用时建表）。

    langgraph-checkpoint-postgres 3.x 的 from_conn_string 是上下文管理器：
    退出上下文会关闭底层连接，因此用 ExitStack 常驻，保证 saver 进程级存活。
    """
    global _saver, _saver_stack
    if _saver is not None:
        return _saver
    with _saver_lock:
        if _saver is None:
            from langgraph.checkpoint.postgres import PostgresSaver

            stack = ExitStack()
            saver = stack.enter_context(PostgresSaver.from_conn_string(_sync_db_url()))
            saver.setup()
            logger.info("PostgreSQL Checkpointer 初始化完成（langgraph_checkpoint 表就绪）")
            _saver = saver
            _saver_stack = stack
    return _saver


def create_checkpointer(backend: str = "postgres") -> Any:
    """统一入口：V2 仅支持 postgres；参数保留以兼容旧调用。"""
    if backend != "postgres":
        raise ValueError(f"V2 仅支持 postgres 记忆后端，收到: {backend}")
    return get_postgres_saver()
