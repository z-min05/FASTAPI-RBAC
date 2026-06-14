import os
import asyncio
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.user import User
from app.dependency import require_permissions
from app.core.pagination import PaginationParams
from app.core.response import Response
from app.schemas.camera import CameraCreate, CameraUpdate, CameraResponse, PTZCommand, PTZPreset
from app.services.camera_service import CameraService
from app.utils.stream_manager import stream_manager

router = APIRouter(prefix="/cameras", tags=["摄像头管理"])


@router.get("", summary="获取摄像头列表")
async def get_cameras(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:list")),
):
    service = CameraService(db)
    result = await service.get_cameras(params)
    return Response.success(data=result.model_dump())


@router.get("/{camera_id}", summary="获取摄像头详情")
async def get_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:detail")),
):
    service = CameraService(db)
    camera = await service.get_camera(camera_id)
    return Response.success(data=CameraResponse.model_validate(camera).model_dump())


@router.post("", summary="创建摄像头")
async def create_camera(
    data: CameraCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:create")),
):
    service = CameraService(db)
    camera = await service.create_camera(data)
    return Response.success(data=CameraResponse.model_validate(camera).model_dump())


@router.put("/{camera_id}", summary="更新摄像头")
async def update_camera(
    camera_id: int,
    data: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:update")),
):
    service = CameraService(db)
    camera = await service.update_camera(camera_id, data)
    return Response.success(data=CameraResponse.model_validate(camera).model_dump())


@router.delete("/{camera_id}", summary="删除摄像头")
async def delete_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:delete")),
):
    service = CameraService(db)
    await service.delete_camera(camera_id)
    return Response.success(message="删除成功")


# ---- 连接管理 ----

@router.post("/{camera_id}/connect", summary="连接摄像头")
async def connect_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:connect")),
):
    service = CameraService(db)
    result = await service.connect_camera(camera_id)
    return Response.success(data=result)


@router.post("/{camera_id}/disconnect", summary="断开摄像头")
async def disconnect_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:connect")),
):
    service = CameraService(db)
    result = await service.disconnect_camera(camera_id)
    return Response.success(data=result)


# ---- 云台控制 ----

@router.post("/{camera_id}/ptz", summary="云台控制")
async def ptz_control(
    camera_id: int,
    command: PTZCommand,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:ptz")),
):
    service = CameraService(db)
    result = await service.ptz_control(camera_id, command)
    return Response.success(data=result)


@router.post("/{camera_id}/ptz/stop", summary="停止云台")
async def ptz_stop(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:ptz")),
):
    service = CameraService(db)
    result = await service.ptz_stop(camera_id)
    return Response.success(data=result)


@router.post("/{camera_id}/ptz/preset", summary="调用预置位")
async def ptz_preset(
    camera_id: int,
    preset: PTZPreset,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:ptz")),
):
    service = CameraService(db)
    result = await service.ptz_preset(camera_id, preset.preset_token)
    return Response.success(data=result)


# ---- 抓图 ----

@router.post("/{camera_id}/snapshot", summary="抓图")
async def snapshot(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:snapshot")),
):
    service = CameraService(db)
    result = await service.snapshot(camera_id)
    return Response.success(data=result)


@router.get("/{camera_id}/snapshot/{filename}", summary="下载抓图")
async def download_snapshot(
    camera_id: int,
    filename: str,
    current_user: User = Depends(require_permissions("camera:snapshot")),
):
    filepath = os.path.join(os.getcwd(), "snapshots", filename)
    if not os.path.exists(filepath):
        return Response.error(message="文件不存在", code=404)
    return FileResponse(filepath, media_type="image/jpeg", filename=filename)


# ---- 视频流 ----

@router.post("/{camera_id}/stream/start", summary="启动视频流")
async def start_stream(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:stream")),
):
    service = CameraService(db)
    result = await service.start_stream(camera_id)
    return Response.success(data=result)


@router.post("/{camera_id}/stream/stop", summary="停止视频流")
async def stop_stream(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:stream")),
):
    service = CameraService(db)
    result = await service.stop_stream(camera_id)
    return Response.success(data=result)


@router.get("/{camera_id}/stream/status", summary="获取流状态")
async def get_stream_status(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions("camera:stream")),
):
    service = CameraService(db)
    result = await service.get_stream_status(camera_id)
    return Response.success(data=result)


@router.get("/{camera_id}/stream/live.flv", summary="FLV视频流")
async def live_flv(
    camera_id: int,
):
    from fastapi.responses import Response as FastAPIResponse
    # 等待FLV数据就绪（FFmpeg连接RTSP并产出FLV头）
    ready = await asyncio.to_thread(stream_manager.wait_flv_ready, camera_id)
    if not ready:
        return FastAPIResponse(content=b"Stream not ready", status_code=404, media_type="text/plain")

    process = stream_manager.get_process(camera_id)
    if not process or not stream_manager.is_running(camera_id):
        return FastAPIResponse(content=b"Stream not found", status_code=404, media_type="text/plain")

    def iter_stream():
        try:
            # 先读取FLV头验证数据有效性（FLV文件头前3字节为 "FLV"）
            header = process.stdout.read(9)
            if not header or header[:3] != b"FLV":
                logger.warning(f"FLV流数据无效: camera_id={camera_id}, header={header[:20] if header else b''}")
                return
            yield header
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        except Exception:
            pass

    return StreamingResponse(
        iter_stream(),
        media_type="video/x-flv",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )
