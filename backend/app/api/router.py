from fastapi import APIRouter

from app.api.v1.router import router as v1_router


def create_api_router(api_v1_prefix: str) -> APIRouter:
    router = APIRouter()
    router.include_router(v1_router, prefix=api_v1_prefix)
    return router
