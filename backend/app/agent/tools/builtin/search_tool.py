"""内置示例工具：网络搜索（模拟，待替换为真实搜索 API）。"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def search(query: str) -> str:
    """搜索互联网获取实时信息。

    何时使用:
    - 用户询问实时新闻、天气、事件时
    - 需要查找当前数据或公开信息时

    何时不用:
    - 用户只是在做数学计算
    - 问题不涉及外部信息

    Args:
        query: 搜索关键词。
    """
    # TODO: 替换为 Tavily / Serper / DuckDuckGo 等真实搜索 API
    return f"[搜索结果] 关于 '{query}' 的模拟返回：这是一条示例搜索结果。请替换为真实搜索 API。"
