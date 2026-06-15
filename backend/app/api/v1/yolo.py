import os
import shutil
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.dependency import require_permissions, get_current_user
from app.core.pagination import PaginationParams
from app.core.response import Response
from app.schemas.yolo_model import YoloModelCreate, YoloModelUpdate, YoloModelResponse
from app.schemas.detection_task import DetectionTaskCreate, DetectionTaskUpdate, DetectionTaskResponse
from app.schemas.detection_result import DetectionResultResponse
from app.services.yolo_service import YoloModelService, DetectionTaskService, start_task_scheduler, stop_task_scheduler, get_running_task_ids
from app.utils.logger import logger

router = APIRouter(prefix="/yolo", tags=["YOLO识别管理"])

# 模型文件保存目录
MODEL_DIR = os.path.join(os.getcwd(), "yolo_models")
os.makedirs(MODEL_DIR, exist_ok=True)


# ==================== YOLO模型管理 ====================

@router.get("/models", summary="获取YOLO模型列表")
async def get_yolo_models(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:model:list")),
):
    service = YoloModelService(db)
    result = await service.get_models(params)
    return Response.success(data=result.model_dump())


@router.get("/models/{model_id}", summary="获取YOLO模型详情")
async def get_yolo_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:model:detail")),
):
    service = YoloModelService(db)
    model = await service.get_model(model_id)
    return Response.success(data=YoloModelResponse.model_validate(model).model_dump())


@router.post("/models", summary="创建YOLO模型")
async def create_yolo_model(
    name: str = Form(...),
    version: str = Form(...),
    classes: str = Form(...),
    file: UploadFile = File(...),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:model:create")),
):
    # 保存上传的模型文件
    if not file.filename.endswith('.pt'):
        return Response.error(message="模型文件必须是.pt格式")
    save_path = os.path.join(MODEL_DIR, f"{version}_{file.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    logger.info(f"YOLO模型文件已保存: {save_path}")

    data = YoloModelCreate(
        name=name,
        version=version,
        file_path=save_path,
        classes=classes,
        description=description
    )
    service = YoloModelService(db)
    model = await service.create_model(data)
    return Response.success(data=YoloModelResponse.model_validate(model).model_dump())


@router.put("/models/{model_id}", summary="更新YOLO模型")
async def update_yolo_model(
    model_id: int,
    name: str = Form(None),
    version: str = Form(None),
    classes: str = Form(None),
    description: str = Form(None),
    is_active: bool = Form(None),
    file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:model:update")),
):
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if version is not None:
        update_data["version"] = version
    if classes is not None:
        update_data["classes"] = classes
    if description is not None:
        update_data["description"] = description
    if is_active is not None:
        update_data["is_active"] = is_active

    # 如果上传了新模型文件
    if file and file.filename:
        if not file.filename.endswith('.pt'):
            return Response.error(message="模型文件必须是.pt格式")
        ver = version or f"model_{model_id}"
        save_path = os.path.join(MODEL_DIR, f"{ver}_{file.filename}")
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        update_data["file_path"] = save_path
        logger.info(f"YOLO模型文件已更新: {save_path}")

    data = YoloModelUpdate(**update_data)
    service = YoloModelService(db)
    model = await service.update_model(model_id, data)
    return Response.success(data=YoloModelResponse.model_validate(model).model_dump())


@router.delete("/models/{model_id}", summary="删除YOLO模型")
async def delete_yolo_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:model:delete")),
):
    service = YoloModelService(db)
    await service.delete_model(model_id)
    return Response.success(message="删除成功")


# ==================== 识别任务管理 ====================

@router.get("/tasks", summary="获取识别任务列表")
async def get_detection_tasks(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:task:list")),
):
    service = DetectionTaskService(db)
    result = await service.get_tasks(params)
    return Response.success(data=result.model_dump())


@router.get("/tasks/{task_id}", summary="获取识别任务详情")
async def get_detection_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:task:detail")),
):
    service = DetectionTaskService(db)
    task = await service.get_task(task_id)
    return Response.success(data=DetectionTaskResponse.model_validate(task).model_dump())


@router.post("/tasks", summary="创建识别任务")
async def create_detection_task(
    data: DetectionTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:task:create")),
):
    service = DetectionTaskService(db)
    task = await service.create_task(data)
    return Response.success(data=DetectionTaskResponse.model_validate(task).model_dump())


@router.put("/tasks/{task_id}", summary="更新识别任务")
async def update_detection_task(
    task_id: int,
    data: DetectionTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:task:update")),
):
    service = DetectionTaskService(db)
    task = await service.update_task(task_id, data)
    return Response.success(data=DetectionTaskResponse.model_validate(task).model_dump())


@router.delete("/tasks/{task_id}", summary="删除识别任务")
async def delete_detection_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:task:delete")),
):
    service = DetectionTaskService(db)
    await service.delete_task(task_id)
    return Response.success(message="删除成功")


@router.post("/tasks/{task_id}/toggle", summary="启停识别任务")
async def toggle_detection_task(
    task_id: int,
    active: bool = Query(..., description="是否启用"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:task:toggle")),
):
    service = DetectionTaskService(db)
    task = await service.toggle_task(task_id, active)
    if active:
        start_task_scheduler(task_id, task.interval_seconds, AsyncSessionLocal)
    return Response.success(data=DetectionTaskResponse.model_validate(task).model_dump())


@router.post("/tasks/{task_id}/run", summary="手动执行一次识别")
async def run_detection_once(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:task:run")),
):
    service = DetectionTaskService(db)
    result = await service.run_detection_once(task_id)
    return Response.success(data=DetectionResultResponse.model_validate(result).model_dump())


@router.get("/tasks/running", summary="获取正在运行的任务列表")
async def get_running_tasks(
    current_user: User = Depends(require_permissions("yolo:task:list")),
):
    return Response.success(data=get_running_task_ids())


# ==================== 识别结果管理 ====================

@router.get("/results/{task_id}", summary="获取识别结果列表")
async def get_detection_results(
    task_id: int,
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:result:list")),
):
    service = DetectionTaskService(db)
    result = await service.get_results_paginated(task_id, params)
    return Response.success(data=result.model_dump())


@router.get("/result/{result_id}", summary="获取识别结果详情")
async def get_detection_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("yolo:result:detail")),
):
    service = DetectionTaskService(db)
    result = await service.get_result(result_id)
    return Response.success(data=DetectionResultResponse.model_validate(result).model_dump())


@router.get("/result/{result_id}/image", summary="获取原始图片")
async def get_result_image(
    result_id: int,
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # 支持query参数token用于img标签
    if token:
        try:
            from app.dependency import get_current_user
            from fastapi import Request
            # 手动验证token
            from app.security import decode_token
            from app.exceptions import UnauthorizedException
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise UnauthorizedException("无效的访问令牌")
        except Exception:
            from fastapi.responses import Response as FastAPIResponse
            return FastAPIResponse(content=b"Unauthorized", status_code=401)
    else:
        # 走标准OAuth2认证
        from app.dependency import get_current_active_user
        user = await get_current_active_user(db=db)
    service = DetectionTaskService(db)
    result = await service.get_result(result_id)
    if not os.path.exists(result.image_path):
        return Response.error(message="图片文件不存在")
    return FileResponse(result.image_path, media_type="image/jpeg")


@router.get("/result/{result_id}/annotated", summary="获取标注图片")
async def get_result_annotated(
    result_id: int,
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if token:
        try:
            from app.security import decode_token
            from app.exceptions import UnauthorizedException
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise UnauthorizedException("无效的访问令牌")
        except Exception:
            from fastapi.responses import Response as FastAPIResponse
            return FastAPIResponse(content=b"Unauthorized", status_code=401)
    else:
        from app.dependency import get_current_active_user
        user = await get_current_active_user(db=db)
    service = DetectionTaskService(db)
    result = await service.get_result(result_id)
    if not result.annotated_image_path or not os.path.exists(result.annotated_image_path):
        return Response.error(message="标注图片不存在")
    return FileResponse(result.annotated_image_path, media_type="image/jpeg")
