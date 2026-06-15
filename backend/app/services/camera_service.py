import os
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.camera import Camera
from app.repositories.camera_repo import CameraRepository
from app.schemas.camera import CameraCreate, CameraUpdate, PTZCommand
from app.exceptions import NotFoundException, ConflictException, BadRequestException
from app.utils.logger import logger
from app.utils.onvif_client import OnvifClient
from app.utils.stream_manager import stream_manager


class CameraService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.camera_repo = CameraRepository(db)

    async def get_camera(self, camera_id: int):
        camera = await self.camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundException("摄像头不存在")
        return camera

    async def get_cameras(self, params):
        return await self.camera_repo.get_paginated(params)

    async def create_camera(self, data: CameraCreate):
        existing = await self.camera_repo.get_by_ip(data.ip, data.port)
        if existing:
            raise ConflictException(f"IP {data.ip}:{data.port} 的摄像头已存在")
        camera = Camera(**data.model_dump())
        return await self.camera_repo.create(camera)

    async def update_camera(self, camera_id: int, data: CameraUpdate):
        update_data = data.model_dump(exclude_unset=True)
        camera = await self.camera_repo.update(camera_id, update_data)
        if not camera:
            raise NotFoundException("摄像头不存在")
        # IP/端口/密码变更时使连接缓存失效
        if any(k in update_data for k in ("ip", "port", "username", "password")):
            OnvifClient.invalidate(camera_id)
        return camera

    async def delete_camera(self, camera_id: int):
        stream_manager.stop_stream(camera_id)
        OnvifClient.invalidate(camera_id)
        if not await self.camera_repo.delete(camera_id):
            raise NotFoundException("摄像头不存在")

    # ---- ONVIF 连接 ----
    async def connect_camera(self, camera_id: int):
        camera = await self.get_camera(camera_id)
        try:
            # 使旧缓存失效，强制重新连接
            OnvifClient.invalidate(camera_id)
            onvif_client = await OnvifClient.get(camera)
            stream_uri = await onvif_client.get_stream_uri()
            snapshot_uri = await onvif_client.get_snapshot_uri()
            update_data = {}
            if stream_uri and not camera.rtsp_url:
                update_data["rtsp_url"] = stream_uri
            if snapshot_uri and not camera.snapshot_url:
                update_data["snapshot_url"] = snapshot_uri
            update_data["is_online"] = True
            if update_data:
                camera = await self.camera_repo.update(camera_id, update_data)
            return {"status": "connected", "rtsp_url": camera.rtsp_url, "snapshot_url": camera.snapshot_url}
        except Exception as e:
            await self.camera_repo.update(camera_id, {"is_online": False})
            OnvifClient.invalidate(camera_id)
            logger.error(f"摄像头 {camera_id} 连接失败: {e}")
            raise BadRequestException(f"摄像头连接失败: {str(e)}")

    async def disconnect_camera(self, camera_id: int):
        stream_manager.stop_stream(camera_id)
        OnvifClient.invalidate(camera_id)
        await self.camera_repo.update(camera_id, {"is_online": False})
        return {"status": "disconnected"}

    # ---- 云台控制 ----
    async def ptz_control(self, camera_id: int, command: PTZCommand):
        camera = await self.get_camera(camera_id)
        if not camera.is_online:
            raise BadRequestException("摄像头不在线，无法控制云台")
        try:
            onvif_client = await OnvifClient.get(camera)
            await onvif_client.ptz_move(command.pan, command.tilt, command.zoom)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"摄像头 {camera_id} 云台控制失败: {e}")
            OnvifClient.invalidate(camera_id)
            raise BadRequestException(f"云台控制失败: {str(e)}")

    async def ptz_stop(self, camera_id: int):
        camera = await self.get_camera(camera_id)
        if not camera.is_online:
            raise BadRequestException("摄像头不在线")
        try:
            onvif_client = await OnvifClient.get(camera)
            await onvif_client.ptz_stop()
            return {"status": "ok"}
        except Exception as e:
            OnvifClient.invalidate(camera_id)
            raise BadRequestException(f"云台停止失败: {str(e)}")

    async def ptz_preset(self, camera_id: int, preset_token: str):
        camera = await self.get_camera(camera_id)
        if not camera.is_online:
            raise BadRequestException("摄像头不在线")
        try:
            onvif_client = await OnvifClient.get(camera)
            await onvif_client.goto_preset(preset_token)
            return {"status": "ok"}
        except Exception as e:
            OnvifClient.invalidate(camera_id)
            raise BadRequestException(f"预置位调用失败: {str(e)}")

    # ---- 抓图 ----
    async def snapshot(self, camera_id: int):
        camera = await self.get_camera(camera_id)
        if not camera.is_online:
            raise BadRequestException("摄像头不在线，无法抓图")

        snapshot_dir = os.path.join(os.getcwd(), "snapshots")
        os.makedirs(snapshot_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"camera_{camera_id}_{timestamp}.jpg"
        filepath = os.path.join(snapshot_dir, filename)

        try:
            # 优先用已有的snapshot_url直接下载，无需ONVIF连接
            snap_url = camera.snapshot_url
            if not snap_url:
                onvif_client = await OnvifClient.get(camera)
                snap_url = await onvif_client.get_snapshot_uri()
            if not snap_url:
                raise BadRequestException("无法获取抓图URL")

            import httpx
            if camera.username and camera.password:
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(snap_url)
                auth_netloc = f"{camera.username}:{camera.password}@{parsed.hostname}"
                if parsed.port:
                    auth_netloc += f":{parsed.port}"
                snap_url = urlunparse(parsed._replace(netloc=auth_netloc))

            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.get(snap_url)
                resp.raise_for_status()
                with open(filepath, "wb") as f:
                    f.write(resp.content)

            logger.info(f"摄像头 {camera_id} 抓图成功: {filepath}")
            return {"filename": filename, "path": filepath}
        except BadRequestException:
            raise
        except Exception as e:
            logger.error(f"摄像头 {camera_id} 抓图失败: {e}")
            OnvifClient.invalidate(camera_id)
            raise BadRequestException(f"抓图失败: {str(e)}")

    # ---- 视频流 ----
    async def start_stream(self, camera_id: int):
        camera = await self.get_camera(camera_id)
        if not camera.rtsp_url:
            raise BadRequestException("摄像头未配置RTSP流地址")
        if not camera.is_online:
            raise BadRequestException("摄像头不在线")

        try:
            stream_url = await asyncio.to_thread(stream_manager.start_stream, camera_id, camera.rtsp_url)
        except RuntimeError as e:
            raise BadRequestException(str(e))
        return {"stream_url": stream_url}

    async def stop_stream(self, camera_id: int):
        await asyncio.to_thread(stream_manager.stop_stream, camera_id)
        return {"status": "stopped"}

    async def get_stream_status(self, camera_id: int):
        is_running = stream_manager.is_running(camera_id)
        return {"is_running": is_running, "stream_url": f"/api/v1/cameras/{camera_id}/stream/live.flv" if is_running else None}
