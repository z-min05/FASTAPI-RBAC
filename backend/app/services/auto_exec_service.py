"""自动化用例异步执行服务
通过 subprocess 调用 pytest 执行单个用例函数，异步完成后更新数据库。
执行后自动读取项目日志文件中的用例日志，写入结果描述。
"""
import asyncio
import os
import re
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# 存储后台任务引用，避免被 GC 回收
_running_tasks: set = set()


# ---------- 日志提取 ----------

def _extract_last_test_log_from_file(log_path: str, test_func: str) -> str | None:
    """从单个日志文件提取该用例**最后一次**执行的日志（从最后一次 start 到最后一次 end）"""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None

    start_marker = f"用例开始: {test_func}_"
    end_marker = f"用例结束: {test_func}_"

    # 从后向前扫描，找最后一次出现的 start 和 end
    last_start = -1
    last_end = -1
    for i in reversed(range(len(lines))):
        line = lines[i]
        if last_start == -1 and start_marker in line:
            last_start = i
        if last_start != -1 and last_end == -1 and end_marker in line:
            last_end = i
            break

    # 如果没找到完整的 start+end，就只取最后一次 start 到文件末尾
    if last_start == -1:
        # 这个文件没有该用例，返回 None
        return None
    if last_end == -1:
        # 用例还在写，但是到文件末尾了
        selected = lines[last_start:]
    else:
        selected = lines[last_start : last_end + 1]

    text = "".join(selected).strip()
    return text if text else None


def _find_last_test_log(log_dir: str, test_func: str) -> str | None:
    """按修改时间从新到旧扫描所有 log 文件，找到该测试函数最近一次执行的完整日志"""
    if not os.path.isdir(log_dir):
        return None

    candidates = [
        os.path.join(log_dir, f)
        for f in os.listdir(log_dir)
        if f.endswith(".log")
    ]
    if not candidates:
        return None

    # 从新到旧排序（越新的文件越先检查）
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    for fpath in candidates:
        text = _extract_last_test_log_from_file(fpath, test_func)
        if text:
            return text

    return None


# ---------- pytest 结果解析 ----------

def _parse_pytest_result(stdout: str, stderr: str) -> tuple[str, str]:
    """解析 pytest 输出，返回 (result: pass/fail, detail: str)"""
    text = stdout + "\n" + stderr
    passed = len(re.findall(r"(\d+) passed", text))
    failed = len(re.findall(r"(\d+) failed", text))
    errors = len(re.findall(r"(\d+) error", text))

    if failed > 0 or errors > 0:
        fail_lines = []
        for line in (stdout + "\n" + stderr).splitlines():
            if "FAILED" in line or "AssertionError" in line or "Error" in line:
                fail_lines.append(line.strip())
        detail = "FAILED\n" + "\n".join(fail_lines[:20]) if fail_lines else "FAILED (see pytest output)"
        return "fail", detail
    elif passed > 0:
        return "pass", f"PASSED ({text.strip().splitlines()[-1] if text.strip() else ''})"
    else:
        tail = "\n".join(text.strip().splitlines()[-5:]) if text.strip() else ""
        return "fail", f"NO_RESULT_MATCHED\n{tail}" if tail else "NO_RESULT_MATCHED"


# ---------- 执行 ----------

async def _run_pytest_async(
    python_path: str,
    test_file: str,
    test_func: str,
    cwd: str,
    timeout: int = 120,
) -> tuple[str, str]:
    """异步执行 pytest 单个函数，返回 (result, result_desc)"""
    loop = asyncio.get_running_loop()

    def _run():
        cmd = [
            python_path,
            "-m", "pytest",
            f"{test_file}::{test_func}",
            "-v",
            "--no-header",
            "-q",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result, detail = _parse_pytest_result(proc.stdout, proc.stderr)
            return result, detail
        except subprocess.TimeoutExpired:
            return "fail", "TIMEOUT: 执行超时 ({}秒)".format(timeout)
        except FileNotFoundError:
            return "fail", "Python 解释器路径不存在: {}".format(python_path)
        except Exception as e:
            return "fail", "EXEC_ERROR: {}".format(str(e))

    result, detail = await loop.run_in_executor(None, _run)

    # 按修改时间从新到旧扫描日志文件，找到该用例最近一次执行的完整日志
    log_dir = os.path.join(cwd, "logs")
    log_text = _find_last_test_log(log_dir, test_func)
    if log_text:
        time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        detail = f"[{time_str}] {result.upper()}\n{log_text}"

    return result, detail


async def execute_testcase_background(
    db_session_factory,
    plan_id: int,
    ptc_id: int,
    python_path: str,
    test_file: str,
    test_func: str,
    cwd: str,
    tester_id: int | None,
) -> None:
    """后台执行单个用例，完成后更新数据库结果"""
    result, result_desc = await _run_pytest_async(python_path, test_file, test_func, cwd)

    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.plan_testcase import PlanTestCase

    async with db_session_factory() as session:
        session: AsyncSession
        pt = await session.get(PlanTestCase, ptc_id)
        if not pt or pt.plan_id != plan_id:
            return

        if result == "pass":
            pt.result = "pass"
        else:
            pt.result = "fail"
        pt.result_desc = result_desc
        if tester_id:
            pt.tester_id = tester_id
        await session.commit()


async def _execute_cases_sequential(
    db_session_factory,
    plan_id: int,
    entries: list[tuple[int, int, str, str]],
    python_path: str,
    cwd: str,
    current_tester_id: int | None,
) -> None:
    """批量串行执行多个用例，一个接一个，每次完成更新结果"""
    for ptc_id, _, test_file, test_func in entries:
        # 更新数据库标记为执行中
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.plan_testcase import PlanTestCase

        async with db_session_factory() as session:
            pt = await session.get(PlanTestCase, ptc_id)
            if pt and pt.plan_id == plan_id and pt.result == "running":
                pt.result_desc = "正在执行中..."
                if current_tester_id:
                    pt.tester_id = current_tester_id
                await session.commit()

        # 执行单个
        result, result_desc = await _run_pytest_async(python_path, test_file, test_func, cwd)

        # 更新结果
        async with db_session_factory() as session:
            pt = await session.get(PlanTestCase, ptc_id)
            if not pt or pt.plan_id != plan_id:
                continue
            if result == "pass":
                pt.result = "pass"
            else:
                pt.result = "fail"
            pt.result_desc = result_desc
            if current_tester_id:
                pt.tester_id = current_tester_id
            await session.commit()