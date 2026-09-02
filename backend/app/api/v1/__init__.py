from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.roles import router as roles_router
from app.api.v1.permissions import router as permissions_router
from app.api.v1.menus import router as menus_router
from app.api.v1.departments import router as departments_router
from app.api.v1.logs import router as logs_router
from app.api.v1.projects import router as projects_router
from app.api.v1.testcases import router as testcases_router
from app.api.v1.agent import router as agent_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(permissions_router)
router.include_router(menus_router)
router.include_router(departments_router)
router.include_router(logs_router)
router.include_router(projects_router)
router.include_router(testcases_router)
router.include_router(agent_router)
