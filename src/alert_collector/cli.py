"""Typer CLI entrypoint."""

import json
import logging
from dataclasses import asdict

import typer
import uvicorn

from alert_collector.api.app import create_app
from alert_collector.logging import configure_logging
from alert_collector.sync import SyncExternalFailureError, SyncLockUnavailableError, SyncService
from alert_collector.worker.celery_app import celery_app

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
def run_worker(log_level: str = typer.Option("INFO", help="Celery worker log level.")) -> None:
    """Run Celery worker process."""
    configure_logging(getattr(logging, log_level.upper(), logging.INFO))
    celery_app.worker_main(["worker", "--loglevel", log_level.lower()])


@app.command("beat")
def run_beat(log_level: str = typer.Option("INFO", help="Celery beat log level.")) -> None:
    """Run Celery beat scheduler process."""
    configure_logging(getattr(logging, log_level.upper(), logging.INFO))
    celery_app.worker_main(["beat", "--loglevel", log_level.lower()])


@app.command("sync-once")
def run_sync_once() -> None:
    """Execute one sync run directly from CLI."""
    configure_logging()
    try:
        result = SyncService().sync_alerts()
    except SyncExternalFailureError as exc:
        typer.echo(f"External sync failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except SyncLockUnavailableError as exc:
        typer.echo(f"Sync lock unavailable: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    payload = asdict(result)
    payload["sync_run_id"] = str(result.sync_run_id)
    payload["since"] = result.since.isoformat()
    payload["up_to"] = result.up_to.isoformat()
    payload["alerts"] = [asdict(alert) for alert in result.alerts]
    typer.echo(json.dumps(payload, default=str))


if __name__ == "__main__":
    app()

