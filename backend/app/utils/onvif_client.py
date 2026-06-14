import asyncio
import threading
import time

from app.utils.logger import logger


class OnvifClient:
    """ONVIF摄像头客户端封装（onvif-zeep是同步库，用asyncio.to_thread包装）"""

    # 连接池缓存: camera_id -> (client, last_used_time)
    _pool: dict[int, tuple["OnvifClient", float]] = {}
    _pool_lock = threading.Lock()
    # 连接缓存过期时间（秒）
    _POOL_TTL: float = 300.0

    def __init__(self, camera):
        self.camera = camera
        self.cam = None
        self.media_service = None
        self.ptz_service = None

    @classmethod
    async def get(cls, camera) -> "OnvifClient":
        """从连接池获取或创建ONVIF客户端"""
        camera_id = camera.id
        with cls._pool_lock:
            if camera_id in cls._pool:
                client, last_used = cls._pool[camera_id]
                if time.monotonic() - last_used < cls._POOL_TTL and client.cam is not None:
                    cls._pool[camera_id] = (client, time.monotonic())
                    logger.debug(f"复用ONVIF连接: camera_id={camera_id}")
                    return client
                else:
                    # 过期或无效，移除
                    del cls._pool[camera_id]

        # 新建连接
        client = cls(camera)
        await client.connect()
        with cls._pool_lock:
            cls._pool[camera_id] = (client, time.monotonic())
        return client

    @classmethod
    def invalidate(cls, camera_id: int):
        """使指定摄像头的连接缓存失效"""
        with cls._pool_lock:
            cls._pool.pop(camera_id, None)

    async def connect(self):
        try:
            from onvif import ONVIFCamera
            try:
                self.cam = await asyncio.to_thread(
                    ONVIFCamera,
                    self.camera.ip,
                    self.camera.port,
                    self.camera.username,
                    self.camera.password,
                    no_cache=True
                )
            except Exception as e1:
                logger.warning(f"ONVIF默认连接失败，尝试替代方式: {e1}")
                try:
                    self.cam = await asyncio.to_thread(
                        ONVIFCamera,
                        self.camera.ip,
                        self.camera.port,
                        self.camera.username,
                        self.camera.password,
                        no_cache=True,
                        adjust_time=False
                    )
                except Exception as e2:
                    raise Exception(f"无法连接到 {self.camera.ip}:{self.camera.port}，请检查IP、端口、用户名和密码。错误: {e1}")

            try:
                dev_info = await asyncio.to_thread(self.cam.devicemgmt.GetDeviceInformation)
                logger.info(f"ONVIF设备连接成功: {dev_info}")
            except Exception as e:
                logger.warning(f"获取设备信息失败（连接可能仍可用）: {e}")

            try:
                self.media_service = await asyncio.to_thread(self.cam.create_media_service)
            except Exception as e:
                raise Exception(f"创建媒体服务失败，设备可能不支持媒体服务: {e}")

            try:
                self.ptz_service = await asyncio.to_thread(self.cam.create_ptz_service)
            except Exception as e:
                logger.warning(f"PTZ服务创建失败（设备可能不支持云台）: {e}")
                self.ptz_service = None

        except Exception as e:
            # 连接失败，清除缓存
            self.invalidate(self.camera.id)
            raise Exception(f"ONVIF连接失败: {str(e)}")

    async def get_stream_uri(self):
        try:
            profiles = await asyncio.to_thread(self.media_service.GetProfiles)
            if not profiles:
                return None
            stream_setup = {
                'Stream': 'RTP-Unicast',
                'Transport': {'Protocol': 'RTSP'}
            }
            uri_response = await asyncio.to_thread(
                self.media_service.GetStreamUri,
                {'StreamSetup': stream_setup, 'ProfileToken': profiles[0].token}
            )
            return uri_response.Uri
        except Exception as e:
            logger.warning(f"获取流地址失败: {e}")
            return None

    async def get_snapshot_uri(self):
        try:
            profiles = await asyncio.to_thread(self.media_service.GetProfiles)
            if not profiles:
                return None
            uri_response = await asyncio.to_thread(
                self.media_service.GetSnapshotUri,
                {'ProfileToken': profiles[0].token}
            )
            return uri_response.Uri
        except Exception as e:
            logger.warning(f"获取抓图地址失败: {e}")
            return None

    async def ptz_move(self, pan: float, tilt: float, zoom: float):
        if not self.ptz_service:
            raise Exception("摄像头不支持云台控制")
        profiles = await asyncio.to_thread(self.media_service.GetProfiles)
        request = self.ptz_service.create_type('ContinuousMove')
        request.ProfileToken = profiles[0].token
        request.Velocity = {
            'PanTilt': {'x': pan, 'y': tilt},
            'Zoom': {'x': zoom}
        }
        await asyncio.to_thread(self.ptz_service.ContinuousMove, request)

    async def ptz_stop(self):
        if not self.ptz_service:
            return
        profiles = await asyncio.to_thread(self.media_service.GetProfiles)
        await asyncio.to_thread(
            self.ptz_service.Stop,
            {'ProfileToken': profiles[0].token, 'PanTilt': True, 'Zoom': True}
        )

    async def goto_preset(self, preset_token: str):
        if not self.ptz_service:
            raise Exception("摄像头不支持云台控制")
        profiles = await asyncio.to_thread(self.media_service.GetProfiles)
        request = self.ptz_service.create_type('GotoPreset')
        request.ProfileToken = profiles[0].token
        request.PresetToken = preset_token
        await asyncio.to_thread(self.ptz_service.GotoPreset, request)
