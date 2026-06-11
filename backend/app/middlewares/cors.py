from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.config import settings


def add_cors_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
