"""内置工具：shell 命令执行（workspace 绑定 + 危险命令黑名单 + 超时 + 输出截断）。

设计要点：
- 工作目录由 Agent 的 workspace 决定，未配置时用服务进程当前目录；
- 危险命令（删除根目录、磁盘操作、关机重启等）直接拒绝，不交给 shell；
- 输出重定向到临时文件后只读头尾各若干字节，避免 `yes` 这类命令把服务进程内存打爆；
- 超时时连同子进程一起终止（POSIX 下按进程组杀）。

注意：黑名单是「拦住明显误操作」的护栏，不是安全沙箱。若要执行不可信命令，
必须在容器 / 低权限用户下部署本服务。
"""
from __future__ import annotations

import locale
import os
import re
import signal
import subprocess
import tempfile
from pathlib import Path

from langchain_core.tools import BaseTool, tool

# 注册表中的工具名，运行时按 name 判断是否需要重建绑定
BASH_TOOL_NAME = "bash"

# 超时（秒）
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300
# 单条输出流最多读进内存的字节数（头部 / 尾部）
_HEAD_BYTES = 6000
_TAIL_BYTES = 2000

# 危险命令黑名单：(正则, 拒绝原因)，命中任意一条即拒绝执行
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\b(?:\s+-[^\s]+)*\s+(?:/|/\*|~|\$HOME)(?:\s|$|\*)", "禁止删除根目录或家目录"),
    (r"\b(?:mkfs(?:\.\w+)?|fdisk|parted|wipefs|mkswap|badblocks)\b", "禁止磁盘 / 分区操作"),
    (r"\bdd\b[^;&|]*\bof=/dev/", "禁止向块设备写入数据"),
    (r">\s*/dev/(?:sd|hd|nvme|vd|xvd)\w*", "禁止直接覆盖块设备"),
    (r"\b(?:shutdown|reboot|halt|poweroff)\b", "禁止关机 / 重启"),
    (r"\binit\s+[06]\b", "禁止切换系统运行级别"),
    (r"\bkill(?:all|all5)?\s+(?:-\w+\s+)*(?:-1|1)\b", "禁止杀死全部进程"),
    (r":\s*\(\s*\)\s*\{.*?\}\s*;?\s*:", "禁止 fork 炸弹"),
    (r"\bch(?:mod|own)\b[^;&|]*\s(?:-[a-zA-Z]+\s+)*(?:/|/\*)(?:\s|$)", "禁止修改根目录的权限或属主"),
    (r"\bformat\s+[a-zA-Z]:", "禁止格式化磁盘"),
    (r"\b(?:rd|rmdir)\s+/s\b[^;&|]*\s[a-zA-Z]:\\?\s*$", "禁止删除整个盘符"),
    (r"\bdel\b[^;&|]*/s\b[^;&|]*\s[a-zA-Z]:\\?\s*$", "禁止删除整个盘符"),
]
_BLOCKED_COMPILED = [(re.compile(p, re.IGNORECASE), why) for p, why in _BLOCKED_PATTERNS]

_ENV_INFO = (
    "\n执行环境:\n"
    "- 工作目录: {cwd}\n"
    "- 超时上限: {max_timeout} 秒；单条输出流最多返回约 {kb}KB，超出部分省略\n"
    "- 危险命令（删除根目录、磁盘操作、关机重启等）会被直接拒绝"
)


def _match_blocked(command: str) -> str | None:
    for pattern, why in _BLOCKED_COMPILED:
        if pattern.search(command):
            return why
    return None


def _decode(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # Windows 下 cmd 输出多为 GBK，退回系统默认编码
        return raw.decode(locale.getpreferredencoding(False), errors="replace")


def _collect(fp) -> tuple[str, int]:
    """只读临时文件的头尾若干字节，返回 (文本, 原始字节数)"""
    fp.seek(0, os.SEEK_END)
    size = fp.tell()
    if size == 0:
        return "", 0
    fp.seek(0)
    head = fp.read(min(size, _HEAD_BYTES))
    if size <= _HEAD_BYTES:
        return _decode(head), size
    tail_bytes = min(size - _HEAD_BYTES, _TAIL_BYTES)
    fp.seek(size - tail_bytes)
    tail = fp.read(tail_bytes)
    omitted = size - len(head) - tail_bytes
    return f"{_decode(head)}\n...[中间省略 {omitted} 字节]...\n{_decode(tail)}", size


def _terminate(proc: subprocess.Popen) -> None:
    """超时时终止进程；POSIX 下按进程组杀，避免子进程残留"""
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _run_command(command: str, workspace: str | None, timeout: int | None) -> str:
    if not command or not command.strip():
        return "[错误] 命令为空"

    blocked = _match_blocked(command)
    if blocked:
        return f"[已拒绝] 命中危险命令黑名单（{blocked}）。请改用更安全的命令。"

    cwd = None
    if workspace:
        path = Path(workspace).expanduser()
        if not path.is_dir():
            return f"[错误] 工作目录不存在或不是目录：{workspace}"
        cwd = str(path)

    try:
        seconds = int(timeout) if timeout else DEFAULT_TIMEOUT
    except (TypeError, ValueError):
        seconds = DEFAULT_TIMEOUT
    seconds = max(1, min(seconds, MAX_TIMEOUT))

    popen_kwargs = {}
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True

    with tempfile.TemporaryFile() as out_f, tempfile.TemporaryFile() as err_f:
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=out_f,
                stderr=err_f,
                **popen_kwargs,
            )
        except Exception as exc:
            return f"[执行失败] {type(exc).__name__}: {exc}"

        timed_out = False
        try:
            proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate(proc)
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

        out_text, out_size = _collect(out_f)
        err_text, err_size = _collect(err_f)

    if timed_out:
        parts = [f"[超时] 命令执行超过 {seconds} 秒，已终止。"]
    else:
        parts = [f"退出码: {proc.returncode}"]

    if out_text.strip():
        parts.append(f"--- stdout ({out_size} 字节) ---\n{out_text.rstrip()}")
    if err_text.strip():
        parts.append(f"--- stderr ({err_size} 字节) ---\n{err_text.rstrip()}")
    if len(parts) == 1:
        parts.append("(无输出)")
    return "\n".join(parts)


def build_bash_tool(workspace: str | None = None) -> BaseTool:
    """构造绑定到指定工作目录的 bash 工具。

    Agent 实例构建时按自身 workspace 调用；注册表里另有一个未绑定的实例，
    仅用于「可用工具」列表展示与工具名白名单校验。
    """

    @tool(BASH_TOOL_NAME)
    def bash(command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """在服务器上执行 shell 命令，返回退出码与标准输出 / 错误输出。

        何时使用:
        - 需要查看目录结构、读取文件内容、运行脚本或命令行工具时
        - 需要验证某个命令的输出或运行环境时

        何时不用:
        - 纯数学计算（直接给出结果即可）
        - 需要读写平台自身的数据（请使用平台已有的功能）

        Args:
            command: 要执行的 shell 命令，例如 "ls -la" 或 "python --version"。
            timeout: 超时秒数，默认 60，最大 300。
        """
        return _run_command(command, workspace, timeout)

    bash.description = (bash.description or "") + _ENV_INFO.format(
        cwd=workspace or "（未配置，使用服务进程当前目录）",
        max_timeout=MAX_TIMEOUT,
        kb=(_HEAD_BYTES + _TAIL_BYTES) // 1000,
    )
    return bash


# 供注册表自动发现：未绑定 workspace 的默认实例
bash = build_bash_tool(None)
