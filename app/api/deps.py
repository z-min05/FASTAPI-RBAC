from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependency import get_current_active_user
from app.models.user import User


def get_db_session():
    return Depends(get_db)


def get_current_user():
    return Depends(get_current_active_user)
