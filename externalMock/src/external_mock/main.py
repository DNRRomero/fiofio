import os
import random
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query

from .domain import AlertsEnvelope
from .generate import generate_alerts
from .validate import parse_source_filter, resolve_window
import structlog

app = FastAPI(title="External Mock Alerts Service")

logger = structlog.get_logger()

def parse_bool_env(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.strip().lower() in ("true", "1")


def get_rng() -> random.Random:
    seed = os.getenv("RNG_SEED", default="0")
    return random.Random(int(seed))


@app.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/alerts/", response_model=AlertsEnvelope)
def get_alerts(
    source: Annotated[
        str | None, Query(description="Comma-separated source filter")
    ] = None,
    since: Annotated[str | None, Query(description="ISO8601 datetime")] = None,
    up_to: Annotated[str | None, Query(description="ISO8601 datetime")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> AlertsEnvelope:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    accepted_token = os.getenv("ACCEPTED_TOKEN", "")
    expected_authorization = f"Token {accepted_token}"
    if authorization != expected_authorization:
        raise HTTPException(status_code=403, detail="Invalid API token")

    source_filter = parse_source_filter(source)
    since_dt, up_to_dt = resolve_window(since, up_to)

    if parse_bool_env("FORCE_ERROR"):
        logger.error("Forced internal server error")
        raise HTTPException(status_code=500, detail="Forced internal server error")

    rng = get_rng()
    if rng.random() < 0.2:
        logger.info("Random internal server error")
        raise HTTPException(status_code=500, detail="Internal server error")

    alerts = generate_alerts(rng, since_dt, up_to_dt)
    if source_filter:
        allowed = set(source_filter)
        alerts = [alert for alert in alerts if alert.source in allowed]

    return AlertsEnvelope(alerts=alerts)
