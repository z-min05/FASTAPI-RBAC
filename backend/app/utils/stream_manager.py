import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from app.utils.logger import logger


@dataclass
class StreamContext:
    """单个转码流的上下文信息"""
    camera_id: int
    process: subprocess.Popen
    stderr_thread: threading.Thread
    rtsp_url: str = ""
    stderr_lines: list[str] = field(default_factory=list)
    # FLV头是否已就绪（FFmpeg已产出有效FLV数据）
    flv_ready: threading.Event = field(default_factory=threading.Event)

    @property
    def is_alive(self) -> bool:
        return self.process.poll() is None

    @property
    def exit_code(self) -> Optional[int]:
        return self.process.poll()


class StreamManager:
    """管理FFmpeg RTSP→FLV转码进程（输出到stdout，供StreamingResponse管道转发）

    特性：
    - 线程安全：通过 threading.Lock 保护共享状态
    - 快速启动：start_stream 立即返回，FLV端点等待数据就绪
    - 进程隔离：每个摄像头独立进程，互不影响
    - 优雅停止：先 terminate，超时后 kill
    - stderr 智能日志：错误信息提升到 WARNING，普通输出 DEBUG
    """

    # FFmpeg 搜索路径（按优先级）
    _FFMPEG_CANDIDATES: list[str] = [
        r"D:\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
    ]

    # 输入选项（放在 -i 之前）
    _INPUT_ARGS: list[str] = [
        "-rtsp_transport", "tcp",
        "-analyzeduration", "1000000",
        "-probesize", "1000000",
    ]

    # 输出选项（放在 -i 之后、输出之前）
    _OUTPUT_ARGS: list[str] = [
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "30",
        "-keyint_min", "30",
        "-b:v", "1500k",
        "-maxrate", "2000k",
        "-bufsize", "3000k",
        "-c:a", "aac",
        "-f", "flv",
        "-flvflags", "no_duration_filesize",
    ]

    # FLV端点等待数据就绪的超时（秒）
    FLV_READY_TIMEOUT: float = 10.0

    def __init__(self):
        self._streams: dict[int, StreamContext] = {}
        self._lock = threading.Lock()
        self._ffmpeg_path: Optional[str] = None

    # ---- FFmpeg 路径解析（惰性缓存）----

    def _resolve_ffmpeg(self) -> str:
        if self._ffmpeg_path is not None:
            return self._ffmpeg_path

        # 1. 系统 PATH
        found = shutil.which("ffmpeg")
        if found:
            self._ffmpeg_path = found
            return found

        # 2. 候选路径
        for candidate in self._FFMPEG_CANDIDATES:
            if os.path.isfile(candidate):
                self._ffmpeg_path = candidate
                return candidate

        raise RuntimeError(
            "未找到FFmpeg，请安装FFmpeg并添加到系统PATH，"
            "或在 StreamManager._FFMPEG_CANDIDATES 中配置路径"
        )

    # ---- 进程生命周期 ----

    def start_stream(self, camera_id: int, rtsp_url: str) -> str:
        """启动转码流，立即返回。FLV数据就绪由 wait_flv_ready() 负责。"""
        with self._lock:
            # 已有同 URL 的流在运行，直接复用
            existing = self._streams.get(camera_id)
            if existing and existing.is_alive and existing.rtsp_url == rtsp_url:
                logger.info(f"复用已有流: camera_id={camera_id}")
                return f"/api/v1/cameras/{camera_id}/stream/live.flv"

            # URL 变化或进程已死，先清理
            if existing:
                self._stop_stream_locked(camera_id)

        ffmpeg_path = self._resolve_ffmpeg()

        cmd = [ffmpeg_path] + self._INPUT_ARGS + ["-i", rtsp_url] + self._OUTPUT_ARGS + ["pipe:1"]
        logger.info(f"启动FFmpeg转码: camera_id={camera_id}, rtsp={rtsp_url}")

        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
        )

        stderr_lines: list[str] = []
        flv_ready = threading.Event()

        # 后台线程消费 stderr，防止缓冲区满阻塞进程
        stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(process, camera_id, stderr_lines),
            daemon=True,
            name=f"ffmpeg-stderr-{camera_id}",
        )
        stderr_thread.start()

        # 后台线程检测FLV头就绪
        ready_thread = threading.Thread(
            target=self._detect_flv_ready,
            args=(process, camera_id, flv_ready, stderr_lines),
            daemon=True,
            name=f"ffmpeg-ready-{camera_id}",
        )
        ready_thread.start()

        ctx = StreamContext(
            camera_id=camera_id,
            process=process,
            stderr_thread=stderr_thread,
            rtsp_url=rtsp_url,
            stderr_lines=stderr_lines,
            flv_ready=flv_ready,
        )

        with self._lock:
            self._streams[camera_id] = ctx

        logger.info(f"FFmpeg进程已启动: camera_id={camera_id}, pid={process.pid}")
        return f"/api/v1/cameras/{camera_id}/stream/live.flv"

    def wait_flv_ready(self, camera_id: int, timeout: float = None) -> bool:
        """等待FLV数据就绪。返回True表示就绪，False表示超时或进程已死。"""
        if timeout is None:
            timeout = self.FLV_READY_TIMEOUT
        with self._lock:
            ctx = self._streams.get(camera_id)
        if not ctx:
            return False
        return ctx.flv_ready.wait(timeout=timeout)

    def stop_stream(self, camera_id: int):
        """停止转码流"""
        with self._lock:
            self._stop_stream_locked(camera_id)

    def _stop_stream_locked(self, camera_id: int):
        """内部停止方法，调用方需已持有锁"""
        ctx = self._streams.pop(camera_id, None)
        if not ctx:
            return
        self._terminate_process(ctx.process, camera_id)

    def stop_all(self):
        """停止所有转码流"""
        with self._lock:
            camera_ids = list(self._streams.keys())
            for cid in camera_ids:
                self._stop_stream_locked(cid)

    # ---- 状态查询 ----

    def is_running(self, camera_id: int) -> bool:
        with self._lock:
            ctx = self._streams.get(camera_id)
            return ctx is not None and ctx.is_alive

    def get_process(self, camera_id: int) -> Optional[subprocess.Popen]:
        with self._lock:
            ctx = self._streams.get(camera_id)
            return ctx.process if ctx else None

    def get_stream_info(self, camera_id: int) -> Optional[dict]:
        """获取流详细信息"""
        with self._lock:
            ctx = self._streams.get(camera_id)
            if not ctx:
                return None
            return {
                "camera_id": camera_id,
                "rtsp_url": ctx.rtsp_url,
                "pid": ctx.process.pid,
                "is_alive": ctx.is_alive,
                "flv_ready": ctx.flv_ready.is_set(),
                "exit_code": ctx.exit_code,
            }

    def list_streams(self) -> list[dict]:
        """列出所有活跃流"""
        with self._lock:
            return [
                {
                    "camera_id": cid,
                    "rtsp_url": ctx.rtsp_url,
                    "pid": ctx.process.pid,
                    "is_alive": ctx.is_alive,
                    "flv_ready": ctx.flv_ready.is_set(),
                    "exit_code": ctx.exit_code,
                }
                for cid, ctx in self._streams.items()
            ]

    # ---- 内部工具 ----

    @staticmethod
    def _detect_flv_ready(
        process: subprocess.Popen,
        camera_id: int,
        flv_ready: threading.Event,
        stderr_lines: list[str],
    ):
        """后台线程：检测FFmpeg是否已产出FLV头，或进程是否异常退出"""
        # 轮询检测，最多等 FLV_READY_TIMEOUT 秒
        deadline = time.monotonic() + StreamManager.FLV_READY_TIMEOUT
        while time.monotonic() < deadline:
            if not process.poll() is None:
                # 进程已退出
                exit_code = process.poll()
                error_output = StreamManager._collect_stderr(stderr_lines, max_lines=10)
                logger.error(
                    f"FFmpeg进程异常退出: camera_id={camera_id}, exit_code={exit_code}, "
                    f"stderr={error_output or '无'}"
                )
                return
            # 尝试 peek stdout 看是否有 FLV 头
            # 注意：不能 read，因为会消费数据；用 poll 检测进程存活即可
            # 实际 FLV 头验证在 live_flv 端点做
            # 这里简单等进程存活 1 秒即认为可能就绪
            time.sleep(0.5)
            if process.poll() is None:
                # 进程还活着，标记就绪
                flv_ready.set()
                logger.info(f"FLV流就绪: camera_id={camera_id}")
                return
        # 超时
        logger.warning(f"FLV流就绪超时: camera_id={camera_id}")

    @staticmethod
    def _terminate_process(process: subprocess.Popen, camera_id: int, timeout: float = 5.0):
        """优雅终止进程：先 terminate，超时后 kill"""
        try:
            process.terminate()
            process.wait(timeout=timeout)
            logger.info(f"FFmpeg进程已终止: camera_id={camera_id}, pid={process.pid}")
        except subprocess.TimeoutExpired:
            process.kill()
            logger.warning(f"FFmpeg进程被强制kill: camera_id={camera_id}, pid={process.pid}")
        except Exception as e:
            logger.error(f"停止FFmpeg进程异常: camera_id={camera_id}, error={e}")

    @staticmethod
    def _drain_stderr(process: subprocess.Popen, camera_id: int, lines: list[str]):
        """持续读取stderr，防止缓冲区满导致进程阻塞"""
        try:
            for line in iter(process.stderr.readline, b""):
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str:
                    continue
                lines.append(line_str)
                if len(lines) > 100:
                    del lines[:50]
                lower = line_str.lower()
                if any(kw in lower for kw in ("error", "fail", "invalid", "cannot", "warning", "unable")):
                    logger.warning(f"FFmpeg[camera_{camera_id}]: {line_str}")
                else:
                    logger.debug(f"FFmpeg[camera_{camera_id}]: {line_str}")
        except ValueError:
            pass
        except Exception:
            pass

    @staticmethod
    def _collect_stderr(lines: list[str], max_lines: int = 20) -> str:
        """从 stderr 行列表中提取最近的错误信息"""
        if not lines:
            return ""
        error_lines = [
            l for l in lines
            if any(kw in l.lower() for kw in ("error", "fail", "invalid", "cannot", "unable"))
        ]
        if error_lines:
            return "; ".join(error_lines[-max_lines:])
        return "; ".join(lines[-max_lines:])


# 全局流管理器实例
stream_manager = StreamManager()
