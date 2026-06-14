import os
import json
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.yolo_model import YoloModel
from app.models.detection_task import DetectionTask
from app.models.detection_result import DetectionResult
from app.repositories.yolo_model_repo import YoloModelRepository
from app.repositories.detection_task_repo import DetectionTaskRepository
from app.repositories.detection_result_repo import DetectionResultRepository
from app.repositories.camera_repo import CameraRepository
from app.schemas.yolo_model import YoloModelCreate, YoloModelUpdate
from app.schemas.detection_task import DetectionTaskCreate, DetectionTaskUpdate
from app.exceptions import NotFoundException, ConflictException, BadRequestException
from app.utils.logger import logger


class YoloModelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.model_repo = YoloModelRepository(db)

    async def get_models(self, params):
        return await self.model_repo.get_paginated(params)

    async def get_model(self, model_id: int):
        m = await self.model_repo.get_by_id(model_id)
        if not m:
            raise NotFoundException("YOLO模型不存在")
        return m

    async def create_model(self, data: YoloModelCreate):
        # file_path由API层保存文件后传入，不再验证文件存在
        # 验证classes是合法JSON数组
        try:
            json.loads(data.classes)
        except json.JSONDecodeError:
            raise BadRequestException("classes必须是合法的JSON数组字符串")
        model = YoloModel(**data.model_dump())
        return await self.model_repo.create(model)

    async def update_model(self, model_id: int, data: YoloModelUpdate):
        update_data = data.model_dump(exclude_unset=True)
        if "file_path" in update_data and not os.path.exists(update_data["file_path"]):
            raise BadRequestException(f"模型文件不存在: {update_data['file_path']}")
        if "classes" in update_data:
            try:
                json.loads(update_data["classes"])
            except json.JSONDecodeError:
                raise BadRequestException("classes必须是合法的JSON数组字符串")
        m = await self.model_repo.update(model_id, update_data)
        if not m:
            raise NotFoundException("YOLO模型不存在")
        return m

    async def delete_model(self, model_id: int):
        if not await self.model_repo.delete(model_id):
            raise NotFoundException("YOLO模型不存在")


class DetectionTaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = DetectionTaskRepository(db)
        self.model_repo = YoloModelRepository(db)
        self.camera_repo = CameraRepository(db)
        self.result_repo = DetectionResultRepository(db)

    async def get_tasks(self, params):
        return await self.task_repo.get_paginated(params)

    async def get_task(self, task_id: int):
        t = await self.task_repo.get_by_id(task_id)
        if not t:
            raise NotFoundException("识别任务不存在")
        return t

    async def create_task(self, data: DetectionTaskCreate):
        # 验证摄像头存在
        camera = await self.camera_repo.get_by_id(data.camera_id)
        if not camera:
            raise NotFoundException("摄像头不存在")
        # 验证模型存在
        model = await self.model_repo.get_by_id(data.model_id)
        if not model:
            raise NotFoundException("YOLO模型不存在")
        # 验证target_classes是合法JSON数组
        try:
            json.loads(data.target_classes)
        except json.JSONDecodeError:
            raise BadRequestException("target_classes必须是合法的JSON数组字符串")
        task = DetectionTask(**data.model_dump())
        return await self.task_repo.create(task)

    async def update_task(self, task_id: int, data: DetectionTaskUpdate):
        update_data = data.model_dump(exclude_unset=True)
        if "camera_id" in update_data:
            camera = await self.camera_repo.get_by_id(update_data["camera_id"])
            if not camera:
                raise NotFoundException("摄像头不存在")
        if "model_id" in update_data:
            model = await self.model_repo.get_by_id(update_data["model_id"])
            if not model:
                raise NotFoundException("YOLO模型不存在")
        if "target_classes" in update_data:
            try:
                json.loads(update_data["target_classes"])
            except json.JSONDecodeError:
                raise BadRequestException("target_classes必须是合法的JSON数组字符串")
        t = await self.task_repo.update(task_id, update_data)
        if not t:
            raise NotFoundException("识别任务不存在")
        return t

    async def delete_task(self, task_id: int):
        # 停止任务调度
        stop_task_scheduler(task_id)
        if not await self.task_repo.delete(task_id):
            raise NotFoundException("识别任务不存在")

    async def toggle_task(self, task_id: int, active: bool):
        t = await self.task_repo.get_by_id(task_id)
        if not t:
            raise NotFoundException("识别任务不存在")
        update_data = {"is_active": active}
        if not active:
            stop_task_scheduler(task_id)
        t = await self.task_repo.update(task_id, update_data)
        return t

    async def get_results(self, task_id: int, params=None):
        results = await self.result_repo.get_by_task_id(task_id)
        return results

    async def get_results_paginated(self, task_id: int, params):
        from sqlalchemy import select
        filters = [DetectionResult.task_id == task_id]
        return await self.result_repo.get_paginated(params, filters=filters)

    async def get_result(self, result_id: int):
        r = await self.result_repo.get_by_id(result_id)
        if not r:
            raise NotFoundException("识别结果不存在")
        return r

    async def run_detection_once(self, task_id: int):
        """手动触发一次识别"""
        t = await self.task_repo.get_by_id(task_id)
        if not t:
            raise NotFoundException("识别任务不存在")
        camera = await self.camera_repo.get_by_id(t.camera_id)
        if not camera:
            raise NotFoundException("摄像头不存在")
        model = await self.model_repo.get_by_id(t.model_id)
        if not model:
            raise NotFoundException("YOLO模型不存在")
        if not camera.is_online:
            raise BadRequestException("摄像头不在线，无法抓图识别")
        return await self._do_detection(t, camera, model)

    async def _do_detection(self, task: DetectionTask, camera, model: YoloModel):
        """执行一次完整的截图+识别流程"""
        # 1. 截图
        snapshot_dir = os.path.join(os.getcwd(), "snapshots")
        os.makedirs(snapshot_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"detect_{task.id}_{timestamp}.jpg"
        snapshot_path = os.path.join(snapshot_dir, snapshot_filename)

        try:
            import httpx
            snap_url = camera.snapshot_url
            if not snap_url:
                from app.utils.onvif_client import OnvifClient
                onvif_client = await OnvifClient.get(camera)
                snap_url = await onvif_client.get_snapshot_uri()
            if not snap_url:
                raise BadRequestException("无法获取抓图URL")

            if camera.username and camera.password:
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(snap_url)
                auth_netloc = f"{camera.username}:{camera.password}@{parsed.hostname}"
                if parsed.port:
                    auth_netloc += f":{parsed.port}"
                snap_url = urlunparse(parsed._replace(netloc=auth_netloc))

            async with httpx.AsyncClient(timeout=15, verify=False) as client:
                resp = await client.get(snap_url)
                resp.raise_for_status()
                with open(snapshot_path, "wb") as f:
                    f.write(resp.content)
        except BadRequestException:
            raise
        except Exception as e:
            logger.error(f"任务{task.id}截图失败: {e}")
            raise BadRequestException(f"截图失败: {str(e)}")

        # 2. YOLO识别
        target_classes = json.loads(task.target_classes)
        try:
            result_data = await asyncio.to_thread(
                _run_yolo_inference, model.file_path, snapshot_path, target_classes
            )
        except Exception as e:
            logger.error(f"任务{task.id} YOLO识别失败: {e}")
            raise BadRequestException(f"YOLO识别失败: {str(e)}")

        # 3. 保存标注图片
        annotated_path = None
        if result_data["annotated_image"] is not None and result_data["detected_count"] > 0:
            result_dir = os.path.join(os.getcwd(), "detection_results")
            os.makedirs(result_dir, exist_ok=True)
            annotated_filename = f"result_{task.id}_{timestamp}.jpg"
            annotated_path = os.path.join(result_dir, annotated_filename)
            # annotated_image是numpy数组，需要用cv2保存
            import cv2
            cv2.imwrite(annotated_path, result_data["annotated_image"])
            logger.info(f"任务{task.id}标注图片已保存: {annotated_path}")

        # 4. 保存识别结果到数据库
        detections_json = json.dumps(result_data["detections"], ensure_ascii=False)
        result = DetectionResult(
            task_id=task.id,
            image_path=snapshot_path,
            annotated_image_path=annotated_path,
            detections=detections_json,
            detected_count=result_data["detected_count"]
        )
        result = await self.result_repo.create(result)

        # 5. 更新任务最后执行时间
        await self.task_repo.update(task.id, {
            "last_run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        # 6. 提交事务（调度器中不会自动commit）
        await self.db.commit()

        logger.info(f"任务{task.id}识别完成: 检测到{result_data['detected_count']}个目标")
        return result


def _run_yolo_inference(model_path: str, image_path: str, target_classes: list[str]):
    """同步执行YOLO推理（在子线程中运行）"""
    from ultralytics import YOLO
    model = YOLO(model_path)
    results = model(image_path)

    detections = []
    annotated_image = None

    for r in results:
        if annotated_image is None:
            annotated_image = r.plot()  # numpy BGR array
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = r.names[cls_id]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            # 只保留目标类别
            if not target_classes or cls_name in target_classes:
                detections.append({
                    "class": cls_name,
                    "confidence": round(confidence, 3),
                    "bbox": [round(v, 1) for v in [x1, y1, x2, y2]]
                })

    return {
        "detections": detections,
        "detected_count": len(detections),
        "annotated_image": annotated_image
    }


# ---- 后台任务调度器 ----
import asyncio
import threading

_scheduler_lock = threading.Lock()
_running_tasks: dict[int, asyncio.Task] = {}  # task_id -> asyncio.Task


async def _scheduler_loop(task_id: int, interval: int, db_factory):
    """在主事件循环中运行的异步调度循环"""
    try:
        while True:
            try:
                async with db_factory() as db:
                    svc = DetectionTaskService(db)
                    task = await svc.task_repo.get_by_id(task_id)
                    if not task or not task.is_active:
                        break
                    camera = await svc.camera_repo.get_by_id(task.camera_id)
                    model = await svc.model_repo.get_by_id(task.model_id)
                    if camera and model and camera.is_online:
                        try:
                            await svc._do_detection(task, camera, model)
                        except Exception as e:
                            logger.error(f"后台任务{task_id}识别失败: {e}")
            except Exception as e:
                logger.error(f"后台任务{task_id}调度异常: {e}")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
    finally:
        with _scheduler_lock:
            _running_tasks.pop(task_id, None)
        logger.info(f"后台识别任务{task_id}已停止")


def start_task_scheduler(task_id: int, interval: int, db_factory):
    """启动后台识别任务调度（在主事件循环中）"""
    with _scheduler_lock:
        if task_id in _running_tasks:
            return  # 已在运行

    # 获取主事件循环，创建异步任务
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.error(f"无法启动任务{task_id}: 没有运行中的事件循环")
        return

    task = loop.create_task(_scheduler_loop(task_id, interval, db_factory))
    with _scheduler_lock:
        _running_tasks[task_id] = task
    logger.info(f"后台识别任务{task_id}已启动, 间隔{interval}秒")


def stop_task_scheduler(task_id: int):
    """停止后台识别任务"""
    with _scheduler_lock:
        task = _running_tasks.pop(task_id, None)
    if task and not task.done():
        task.cancel()
        logger.info(f"后台识别任务{task_id}已发送停止信号")


def get_running_task_ids() -> list[int]:
    """获取正在运行的任务ID列表"""
    with _scheduler_lock:
        return [tid for tid, t in _running_tasks.items() if not t.done()]
