"""FastAPI application assembly."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi_pagination import add_pagination
from prometheus_client import make_asgi_app

from alert_collector.api.alerts import router as alerts_router
from alert_collector.api.health import router as health_router
from alert_collector.api.sync import router as sync_router
from alert_collector.auth import auth_backend, fastapi_users
from alert_collector.auth.schemas import UserRead, UserUpdate
from alert_collector.settings import ApiSettings
from alert_collector.sync import initialize_sync_service


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = ApiSettings()
    initialize_sync_service(
        external_client_host=settings.external_service_host,
        external_client_token=settings.external_service_token,
        sync_frequency=settings.sync_frequency_minutes,
    )
    yield


def create_app() -> FastAPI:
    """Create and configure the collector API application."""
    app = FastAPI(title="Alert Collector API", version="0.1.0", lifespan=_lifespan)

    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
    app.include_router(sync_router)
    app.include_router(alerts_router)
    app.include_router(health_router)
    app.mount("/metrics", make_asgi_app())
    add_pagination(app)

    @app.get("/ping", response_class=PlainTextResponse, tags=["liveness"])
    def ping() -> str:
        return "pong"

    return app


app = create_app()
