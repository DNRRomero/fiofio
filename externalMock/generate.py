import random
from datetime import datetime, timedelta
from uuid import uuid4

from domain import Alert, DESCRIPTIONS, Severity, Source


def random_datetime_between(
    rng: random.Random, start: datetime, end: datetime
) -> datetime:
    delta_seconds = int((end - start).total_seconds())
    if delta_seconds <= 0:
        return start
    offset = rng.randint(0, delta_seconds)
    return start + timedelta(seconds=offset)


def generate_alerts(
    rng: random.Random, since: datetime, up_to: datetime, count: int = 30
) -> list[Alert]:
    sources = list(Source)
    severities = list(Severity)
    alerts: list[Alert] = []
    for _ in range(count):
        alerts.append(
            Alert(
                id=uuid4(),
                source=rng.choice(sources),
                severity=rng.choice(severities),
                description=rng.choice(DESCRIPTIONS),
                created_at=random_datetime_between(rng, since, up_to),
            )
        )
    return alerts
