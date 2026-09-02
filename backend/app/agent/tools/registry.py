"""工具注册中心。"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from langchain_core.tools import BaseTool

logger = logging.getLogger("agent.tools")


class ToolRegistry:
    """全局工具注册表。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            logger.info("覆盖已有工具: %s", tool.name)
        else:
            logger.debug("已注册工具: %s", tool.name)
        self._tools[tool.name] = tool

    def register_many(self, tools: list[BaseTool]) -> None:
        for t in tools:
            self.register(t)

    def autodiscover(self, package_path: str, exclude: list[str] | None = None) -> None:
        """自动扫描指定包下所有 @tool 装饰器定义的工具。"""
        skip = set(exclude or [])
        try:
            package = importlib.import_module(package_path)
        except ImportError as exc:
            logger.error("无法导入包 %s: %s", package_path, exc)
            return

        for importer, modname, ispkg in pkgutil.walk_packages(
            path=package.__path__,
            prefix=package.__name__ + ".",
        ):
            short_name = modname.rsplit(".", 1)[-1]
            if short_name in skip:
                continue
            try:
                mod = importlib.import_module(modname)
            except Exception:
                logger.exception("导入模块 %s 失败", modname)
                continue
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if isinstance(obj, BaseTool) and not attr_name.startswith("_"):
                    self.register(obj)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_enabled(self, names: list[str]) -> list[BaseTool]:
        """按名称列表过滤，保持配置顺序。"""
        result = []
        missing = []
        for name in names:
            t = self._tools.get(name)
            if t:
                result.append(t)
            else:
                missing.append(name)
        if missing:
            logger.warning("以下工具未找到，跳过: %s", missing)
        return result

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)
