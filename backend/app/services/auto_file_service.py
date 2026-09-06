"""自动化 pytest 用例文件生成服务
根据管理端用例信息，在指定远程路径生成 .py 文件骨架：
- 文件不存在则创建，写入 import pytest / import allure 头部
- 函数不存在则追加，包含 @allure.title 及前置条件/测试步骤/预期结果注释
- 不覆盖、不修改已有内容，仅追加；不包裹在 class 内，由用户手动整理
"""
import os
import re
from pathlib import Path
from typing import Tuple

from app.models.testcase import TestCase
from app.exceptions import BadRequestException


# 合法字符正则：允许字母、数字、下划线、短横线（文件名）；仅允许字母数字下划线（函数名）
# 且必须以 test_ 开头
ALLOW_MODULE_CODE_PATTERN = re.compile(r"^test_[a-zA-Z0-9_\-]+$")
ALLOW_CASE_CODE_PATTERN = re.compile(r"^test_[a-zA-Z0-9_]+$")


def _is_safe_path(root: Path, target: Path) -> bool:
    """校验目标路径是否在 root 目录内（防 ../ 越界）"""
    try:
        return target.resolve().is_relative_to(root.resolve())
    except ValueError:
        return False


def validate_codes(module_code: str | None, case_code: str | None) -> None:
    """校验模块编码和用例编码格式（非空都要校验，任一为空不校验对应项）"""
    if module_code:
        if not ALLOW_MODULE_CODE_PATTERN.fullmatch(module_code):
            raise BadRequestException(
                "模块编码格式不合法：必须以 test_ 开头，仅允许字母、数字、下划线、短横线，不能包含路径分隔符"
            )
    if case_code:
        if not ALLOW_CASE_CODE_PATTERN.fullmatch(case_code):
            raise BadRequestException(
                "用例编码格式不合法：必须以 test_ 开头，仅允许字母、数字、下划线"
            )


def validate_root_path(root_path_str: str) -> Tuple[bool, str]:
    """校验自动化根路径：必须是已存在的可写目录；返回 (ok, error_msg)"""
    try:
        root = Path(root_path_str)
        if not root.exists():
            return False, f"自动化根路径不存在: {root_path_str}"
        if not root.is_dir():
            return False, f"自动化根路径必须是目录: {root_path_str}"
        # 验证可写：尝试创建临时文件
        test_file = root / f".write_test_{os.getpid()}.tmp"
        try:
            with open(test_file, "w") as f:
                f.write("ok")
            test_file.unlink()
        except PermissionError:
            return False, f"自动化根路径无写入权限: {root_path_str}"
        except Exception:
            return False, f"自动化根路径无法写入: {root_path_str}"
        return True, ""
    except Exception as e:
        return False, f"路径校验异常: {str(e)}"


def function_exists(content: str, case_code: str) -> bool:
    """检查文件中是否已有同名函数（按行匹配开头 'def case_code('）"""
    prefix = f"def {case_code}("
    for line in content.splitlines():
        if line.strip().startswith(prefix):
            return True
    return False


def generate_function_text(tc: TestCase) -> str:
    """生成函数文本（含 @allure.title 和注释）"""
    title = tc.title
    escaped_title = title.replace('"', '\\"')
    pre = tc.precondition or ""
    steps = tc.steps or ""
    expect = tc.expected_result or ""

    lines = [
        '@allure.title("{}")'.format(escaped_title),
        "def {}():".format(tc.case_code),
        "    # 前置条件：{}".format(pre.strip()) if pre.strip() else "    # 前置条件：（无）",
        "    # 测试步骤：",
    ]
    # 步骤按换行拆分后每行加 # 前缀缩进
    for step_line in (steps or "").splitlines():
        step_line = step_line.strip()
        if step_line:
            lines.append("    # {}".format(step_line))
    lines.append("    # 预期结果：{}".format(expect.strip()) if expect.strip() else "    # 预期结果：（无）")
    lines.append("    pass")
    return "\n".join(lines)


def generate_automation_file(
    auto_root_path: str,
    tc: TestCase,
) -> Tuple[bool, str]:
    """
    生成/追加自动化用例文件
    返回 (success, message)，success=False 表示生成失败（但用例仍可保存）
    """
    module_code = tc.module_code
    case_code = tc.case_code
    # 只有两者都不为空才生成
    if not (auto_root_path and module_code and case_code):
        return True, ""

    # 格式已在创建/更新前校验过，这里再做一次路径安全校验
    root = Path(auto_root_path)
    file_path = (root / f"{module_code}.py").resolve()
    if not _is_safe_path(root, file_path):
        return False, "模块编码非法，路径越界"

    # 检查函数是否已存在
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if function_exists(content, case_code):
            # 已存在，静默成功
            return True, "函数已存在，跳过生成"
        # 追加：两个空行后写入
        new_content = content.rstrip("\n") + "\n\n" + generate_function_text(tc)
    else:
        # 创建新文件：写入头部导入 + 函数
        new_content = (
            "import pytest\n"
            "import allure\n\n"
            + generate_function_text(tc)
        )

    # 写入文件
    try:
        parent = file_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content + "\n")
        return True, f"已生成/追加到 {file_path}"
    except PermissionError:
        return False, f"权限不足，无法写入文件: {file_path}"
    except Exception as e:
        return False, f"写入文件失败: {str(e)}"
