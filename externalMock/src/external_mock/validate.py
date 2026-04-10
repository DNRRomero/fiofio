from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from .domain import Source


def parse_utc_datetime(raw_value: str, field_name: str) -> datetime:
    try:
        normalized = raw_value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid datetime for '{field_name}'. Expected ISO8601.",
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_source_filter(raw_source: str | None) -> list[Source] | None:
    if raw_source is None:
        return None
    chunks = [part.strip() for part in raw_source.split(",") if part.strip()]
    if not chunks:
        return None

    parsed_sources: list[Source] = []
    invalid_sources: list[str] = []
    for chunk in chunks:
        try:
            parsed_sources.append(Source(chunk))
        except ValueError:
            invalid_sources.append(chunk)

    if invalid_sources:
        allowed = ", ".join(source.value for source in Source)
        raise HTTPException(
            status_code=422,
            detail=f"Invalid source value(s): {', '.join(invalid_sources)}. Allowed values: {allowed}",
        )
    return parsed_sources


def resolve_window(
    since_raw: str | None, up_to_raw: str | None
) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    since = parse_utc_datetime(since_raw, "since") if since_raw else None
    up_to = parse_utc_datetime(up_to_raw, "up_to") if up_to_raw else None

    if since and up_to is None:
        up_to = now
    elif up_to and since is None:
        since = up_to - timedelta(days=30)
    elif since is None and up_to is None:
        up_to = now
        since = now - timedelta(days=30)

    assert since is not None
    assert up_to is not None
    if since > up_to:
        raise HTTPException(
            status_code=422, detail="'since' must be less than or equal to 'up_to'."
        )
    return since, up_to
