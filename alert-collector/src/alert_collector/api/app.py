"""FastAPI application assembly."""

from fastapi import FastAPI

from alert_collector.api.alerts import router as alerts_router
from alert_collector.api.health import router as health_router
from alert_collector.api.sync import router as sync_router

from prometheus_client import make_asgi_app


def create_app() -> FastAPI:
    """Create and configure the collector API application."""
    app = FastAPI(title="Alert Collector API", version="0.1.0")
    app.include_router(sync_router)
    app.include_router(alerts_router)
    app.include_router(health_router)
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
