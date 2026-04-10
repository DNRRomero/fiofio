"""Typer CLI entrypoint."""

import asyncio
import logging

import typer
import uvicorn

from alert_collector.api.app import create_app
from alert_collector.logging import configure_logging
from alert_collector.settings import WorkerSettings
from alert_collector.worker import get_celery_app

app = typer.Typer(help="Alert collector command-line interface.")


@app.command("api")
def run_api(
    host: str = typer.Option("0.0.0.0", help="Bind host for FastAPI."),
    port: int = typer.Option(8000, help="Bind port for FastAPI."),
) -> None:
    """Run the FastAPI application server."""
    configure_logging()
    uvicorn.run(create_app(), host=host, port=port)


@app.command("worker")
def run_worker(
    log_level: str = typer.Option("INFO", help="Celery worker log level."),
) -> None:
    """Run Celery worker process."""
    configure_logging(getattr(logging, log_level.upper(), logging.INFO))
    settings = WorkerSettings()
    celery_app = get_celery_app(settings)
    celery_app.worker_main(["worker", "--loglevel", log_level.lower()])


@app.command("beat")
def run_beat(
    log_level: str = typer.Option("INFO", help="Celery beat log level."),
) -> None:
    """Run Celery beat scheduler process."""
    configure_logging(getattr(logging, log_level.upper(), logging.INFO))
    settings = WorkerSettings()
    celery_app = get_celery_app(settings)
    celery_app.start(["beat", "--loglevel", log_level.lower()])


@app.command("create-user")
def create_user(
    email: str = typer.Option(..., help="Email address for the new user."),
    password: str = typer.Option(..., help="Password for the new user."),
    superuser: bool = typer.Option(False, help="Grant superuser privileges."),
) -> None:
    """Create a new API user in the database."""

    async def _create() -> None:
        from alert_collector.auth.db import get_async_session, get_user_db
        from alert_collector.auth.schemas import UserCreate
        from alert_collector.auth.users import UserManager

        async for session in get_async_session():
            async for user_db in get_user_db(session):
                manager = UserManager(user_db)
                user = await manager.create(
                    UserCreate(
                        email=email,
                        password=password,
                        is_superuser=superuser,
                        is_active=True,
                        is_verified=True,
                    )
                )
                typer.echo(f"Created user id={user.id} email={user.email}")

    asyncio.run(_create())


if __name__ == "__main__":
    app()
