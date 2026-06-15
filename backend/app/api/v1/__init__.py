from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.roles import router as roles_router
from app.api.v1.permissions import router as permissions_router
from app.api.v1.menus import router as menus_router
from app.api.v1.departments import router as departments_router
from app.api.v1.logs import router as logs_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.yolo import router as yolo_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(permissions_router)
router.include_router(menus_router)
router.include_router(departments_router)
router.include_router(logs_router)
router.include_router(cameras_router)
router.include_router(yolo_router)
