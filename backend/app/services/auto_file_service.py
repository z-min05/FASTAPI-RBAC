"""自动化 pytest 用例文件生成服务
根据管理端用例信息，在指定远程路径生成 .py 文件骨架：
- 文件不存在则创建，写入 import pytest / import allure 头部
- 函数不存在则追加，包含 @allure.title 及前置条件/测试步骤/预期结果文档字符串
- 不覆盖、不修改已有内容，仅追加；不包裹在 class 内，由用户手动整理
- 删除用例/模块时同步清理对应自动化代码（仅删除对应函数/文件/目录）
- 模块末级状态变化（新增/删除/移入子模块）时，把父模块磁盘形态对齐为「分组=目录、末级=文件」
"""
import os
import re
import shutil
from pathlib import Path
from typing import Tuple

from app.models.testcase import TestCase
from app.exceptions import BadRequestException


# 模块 code（创建/编辑模块时校验）：字符集与长度，目录名与文件名共用
ALLOW_MODULE_DIR_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,100}$")
# 末级模块 code（创建/编辑用例时校验）：必须是 pytest 文件名
TEST_FILE_CODE_PATTERN = re.compile(r"^test_[A-Za-z0-9_\-]+$")
# 模块相对路径：0..n 级目录 + 末级 test_ 开头的文件名，如 device/test_comm_log
ALLOW_MODULE_CODE_PATTERN = re.compile(r"^(?:[A-Za-z0-9_\-]+/)*test_[A-Za-z0-9_\-]+$")
# 用例函数名：仅允许字母数字下划线，且必须以 test_ 开头
ALLOW_CASE_CODE_PATTERN = re.compile(r"^test_[a-zA-Z0-9_]+$")


def _is_safe_path(root: Path, target: Path) -> bool:
    """校验目标路径是否在 root 目录内（防 ../ 越界）"""
    try:
        return target.resolve().is_relative_to(root.resolve())
    except ValueError:
        return False


def validate_codes(module_code: str | None, case_code: str | None) -> None:
    """校验模块路径和用例编码格式（非空都要校验，任一为空不校验对应项）"""
    if module_code:
        if not ALLOW_MODULE_CODE_PATTERN.fullmatch(module_code):
            raise BadRequestException(
                "模块路径格式不合法：多级目录用 / 分隔，末级必须以 test_ 开头，"
                "仅允许字母、数字、下划线、短横线"
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
    """生成函数文本（含 @allure.title 与文档字符串）"""
    title = tc.title
    escaped_title = title.replace('"', '\\"')
    pre = tc.precondition or ""
    steps = tc.steps or ""
    expect = tc.expected_result or ""

    lines = [
        '@allure.title("{}")'.format(escaped_title),
        "def {}():".format(tc.case_code),
        "    '''",
        "    # 前置条件：{}".format(pre.strip()) if pre.strip() else "    # 前置条件：（无）",
        "    # 测试步骤：",
    ]
    # 步骤按换行拆分后每行加 # 前缀缩进
    for step_line in (steps or "").splitlines():
        step_line = step_line.strip()
        if step_line:
            lines.append("    # {}".format(step_line))
    lines.append("    # 预期结果：{}".format(expect.strip()) if expect.strip() else "    # 预期结果：（无）")
    lines.append("    '''")
    lines.append("    pass")
    return "\n".join(lines)


def generate_automation_file(
    auto_root_path: str,
    tc: TestCase,
) -> Tuple[bool, str]:
    """
    生成/追加自动化用例文件
    - tc.module_code 为模块相对路径（如 device/test_comm_log），由模块树推导
    - 文件不存在则创建（多级目录一并创建）；已存在则只追加用例函数，不覆盖
    - tc.case_code 为空时只创建文件骨架
    返回 (success, message)，success=False 表示生成失败（但用例仍可保存）
    """
    module_code = tc.module_code
    case_code = tc.case_code
    # module_code 恒非空（由模块树推导），这里只要求配置了自动化根路径
    if not (auto_root_path and module_code):
        return True, ""

    # 格式已在创建/更新前校验过，这里再做一次路径安全校验
    root = Path(auto_root_path)
    file_path = (root / f"{module_code}.py").resolve()
    leaf_dir = (root / module_code).resolve()
    if not _is_safe_path(root, file_path):
        return False, "模块路径非法，路径越界"

    # 末级模块路径上残留同名目录会导致「文件 + 目录」共存：空目录先清理，非空则不落盘
    if _is_safe_path(root, leaf_dir) and leaf_dir.is_dir():
        if any(leaf_dir.iterdir()):
            return False, f"模块路径上已存在非空目录，未写入文件（请先处理）: {leaf_dir}"
        leaf_dir.rmdir()

    header = "import pytest\nimport allure\n\n"

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 未填用例编码：文件已存在则无需改动
        if not case_code:
            return True, "文件已存在，跳过生成"
        if function_exists(content, case_code):
            # 已存在，静默成功
            return True, "函数已存在，跳过生成"
        # 追加：两个空行后写入
        new_content = content.rstrip("\n") + "\n\n" + generate_function_text(tc)
    else:
        # 创建新文件：写入头部导入；填了用例编码则一并写入函数
        new_content = header + (generate_function_text(tc) if case_code else "")

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


# ---------- 自动化代码删除 ----------

# 自动生成的文件头内容（仅含这些内容的文件删除函数后一并删除）
GENERATED_HEADER_LINES = {"import pytest", "import allure"}


def _find_function_block(lines: list[str], case_code: str) -> tuple[int, int] | None:
    """定位函数块行区间 [start, end)：start 含函数上方的装饰器，end 为函数体之后"""
    prefix = f"def {case_code}("
    for idx, line in enumerate(lines):
        if not line.strip().startswith(prefix):
            continue
        start = idx
        # 向上并入连续的装饰器行（如 @allure.title(...)）
        while start > 0 and lines[start - 1].strip().startswith("@"):
            start -= 1
        indent = len(line) - len(line.lstrip())
        end = idx + 1
        # 向下吞掉函数体（缩进比 def 更深）与空行
        while end < len(lines):
            current = lines[end]
            if not current.strip():
                end += 1
                continue
            if len(current) - len(current.lstrip()) > indent:
                end += 1
                continue
            break
        # 去掉块尾多余空行
        while end > idx + 1 and not lines[end - 1].strip():
            end -= 1
        return start, end
    return None


def _is_only_generated_header(text: str) -> bool:
    """判断文件是否只剩自动生成的内容（导入、空行、注释）"""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped in GENERATED_HEADER_LINES:
            continue
        return False
    return True


def _normalize_blank_lines(text: str) -> str:
    """归一化空行：连续空行最多保留两行（顶层定义间隔），末尾保留单个换行"""
    lines: list[str] = []
    blank_run = 0
    for line in text.split("\n"):
        if not line.strip():
            blank_run += 1
            if blank_run > 2:
                continue
        else:
            blank_run = 0
        lines.append(line)
    result = "\n".join(lines).strip("\n")
    return result + "\n" if result else ""


def remove_cases_from_file(file_path: Path, case_codes: list[str]) -> Tuple[bool, str]:
    """从文件中删除若干用例函数（含函数上方的装饰器）

    - 函数不存在视为成功（静默跳过）
    - 删除后文件只剩自动生成的文件头时，连同文件一起删除
    返回 (success, message)
    """
    if not file_path.exists():
        return True, ""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"读取文件失败: {str(e)}"

    lines = content.split("\n")
    removed = 0
    for case_code in case_codes:
        block = _find_function_block(lines, case_code)
        if not block:
            continue
        start, end = block
        lines = lines[:start] + lines[end:]
        removed += 1
    if not removed:
        return True, ""

    text = _normalize_blank_lines("\n".join(lines))
    try:
        if _is_only_generated_header(text):
            file_path.unlink()
            return True, f"已删除空文件 {file_path}"
        file_path.write_text(text, encoding="utf-8")
        return True, f"已删除 {removed} 个用例函数（{file_path}）"
    except PermissionError:
        return False, f"权限不足，无法修改文件: {file_path}"
    except Exception as e:
        return False, f"删除自动化代码失败: {str(e)}"


def remove_automation_cases(
    auto_root_path: str,
    items: list[tuple[str | None, str | None]],
) -> Tuple[bool, str]:
    """删除若干用例对应的自动化代码：items 为 [(module_code, case_code), ...]

    同一文件只读写一次；任一编码为空则跳过该用例。
    返回 (success, message)
    """
    if not auto_root_path:
        return True, ""
    root = Path(auto_root_path)
    by_module: dict[str, list[str]] = {}
    for module_code, case_code in items:
        if module_code and case_code:
            by_module.setdefault(module_code, []).append(case_code)
    if not by_module:
        return True, ""

    ok_all = True
    messages: list[str] = []
    for module_code, case_codes in by_module.items():
        file_path = (root / f"{module_code}.py").resolve()
        if not _is_safe_path(root, file_path):
            ok_all = False
            messages.append(f"模块路径非法，已跳过: {module_code}")
            continue
        ok, msg = remove_cases_from_file(file_path, case_codes)
        if not ok:
            ok_all = False
        if msg:
            messages.append(msg)
    return ok_all, "；".join(messages)


def remove_automation_module(auto_root_path: str, module_path: str) -> Tuple[bool, str]:
    """删除模块对应的自动化代码

    - 存在 {module_path}.py → 删除该文件（末级模块，对应 pytest 文件）
    - 存在 {module_path} 目录 → 删除该目录及其内容（分组模块，对应目录）
    返回 (success, message)
    """
    if not (auto_root_path and module_path):
        return True, ""
    root = Path(auto_root_path).resolve()
    try:
        file_path = (root / f"{module_path}.py").resolve()
        dir_path = (root / module_path).resolve()
    except Exception as e:
        return False, f"模块路径非法: {str(e)}"

    for target in (file_path, dir_path):
        if not _is_safe_path(root, target) or target == root:
            return False, "模块路径非法，路径越界"

    try:
        if file_path.is_file():
            file_path.unlink()
            return True, f"已删除文件 {file_path}"
        if dir_path.is_dir():
            shutil.rmtree(dir_path)
            return True, f"已删除目录 {dir_path}"
        return True, "对应自动化代码不存在，跳过"
    except PermissionError:
        return False, f"权限不足，无法删除: {module_path}"
    except Exception as e:
        return False, f"删除自动化代码失败: {str(e)}"


# ---------- 磁盘形态对齐 ----------


def align_module_disk_entity(
    auto_root_path: str,
    module_path: str,
    has_children: bool,
) -> Tuple[bool, str]:
    """把模块的磁盘实体对齐为与其末级状态一致的形态

    - has_children=True（分组模块）：目标为目录；若同名 .py 只含自动生成内容则删除后建目录
    - has_children=False（末级模块）：目标为文件；仅清理遗留空目录，文件仍由挂用例时创建
    只清理空目录与纯自动生成内容的文件，绝不删除用户手写代码；
    存在未自动处理的冲突时返回 (False, 提示)，由调用方记录告警，不影响数据库操作。
    """
    if not (auto_root_path and module_path):
        return True, ""
    root = Path(auto_root_path).resolve()
    try:
        file_path = (root / f"{module_path}.py").resolve()
        dir_path = (root / module_path).resolve()
    except Exception as e:
        return False, f"模块路径非法: {str(e)}"

    for target in (file_path, dir_path):
        if not _is_safe_path(root, target) or target == root:
            return False, "模块路径非法，路径越界"

    try:
        if has_children:
            if file_path.is_file():
                content = file_path.read_text(encoding="utf-8")
                if not _is_only_generated_header(content):
                    return False, (
                        f"磁盘上已存在 {file_path} 且包含手写内容，"
                        "未自动转换为目录，请手动处理后重试"
                    )
                file_path.unlink()
                dir_path.mkdir(parents=True, exist_ok=True)
                return True, f"已由文件转换为目录 {dir_path}"
            if not dir_path.is_dir():
                dir_path.mkdir(parents=True, exist_ok=True)
                return True, f"已创建目录 {dir_path}"
            return True, ""

        # 末级模块：目标为文件，仅清理其路径上遗留的空目录
        if dir_path.is_dir():
            if any(dir_path.iterdir()):
                return False, (
                    f"磁盘上仍存在非空目录 {dir_path}，未清理，"
                    "后续挂用例时请先手动处理"
                )
            dir_path.rmdir()
            return True, f"已清理空目录 {dir_path}"
        return True, ""
    except PermissionError:
        return False, f"权限不足，无法对齐磁盘路径: {module_path}"
    except Exception as e:
        return False, f"对齐磁盘路径失败: {str(e)}"
