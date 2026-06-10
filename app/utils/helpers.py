from datetime import datetime
from typing import Any


def build_tree(items: list[dict[str, Any]], parent_key: str = "parent_id", id_key: str = "id", children_key: str = "children") -> list[dict[str, Any]]:
    """将扁平列表构建为树形结构"""
    item_map: dict[int | None, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    # 深拷贝并初始化 children
    for item in items:
        item_copy = dict(item)
        item_copy[children_key] = []
        item_map[item_copy[id_key]] = item_copy

    # 构建树
    for item in items:
        item_copy = item_map[item[id_key]]
        parent_id = item.get(parent_key)
        if parent_id is None or parent_id == 0:
            roots.append(item_copy)
        elif parent_id in item_map:
            item_map[parent_id][children_key].append(item_copy)

    return roots


def format_datetime(dt: datetime) -> str:
    """格式化 datetime 为字符串"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
