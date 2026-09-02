"""内置工具：calculator（安全计算）、search（搜索，模拟实现）。"""

from app.agent.tools.builtin.calculator_tool import calculator
from app.agent.tools.builtin.search_tool import search

__all__ = ["calculator", "search"]
