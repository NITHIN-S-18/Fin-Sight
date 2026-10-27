from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import create_api_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import ErrorHandlingMiddleware
from app.services.dataset_service import get_dataset_service


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        get_dataset_service()
        yield

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        expose_headers=["Content-Disposition"],
    )
    app.add_middleware(ErrorHandlingMiddleware)

    register_error_handlers(app)
    app.include_router(create_api_router(settings.api_v1_prefix))

    return app


app = create_app()
