# Alert Collector Architecture

This document maps the current `alert-collector` implementation to the running architecture and describes the main request and execution paths with sequence diagrams. It consolidates the service-level runtime notes from `alert-collector/README.md` and the API exposure/authentication decisions in `docs/DECISIONS.md`.

## Components

- **Nginx edge**: publishes the collector on port `8000` and currently forwards `/auth/*`, `/alerts`, `/sync`, and `/health`.
- **API**: FastAPI app (`api/app.py`) exposing auth routes, `/alerts`, `/sync`, `/health`, `/metrics`, and `/ping`.
- **Auth layer**: `fastapi-users` with database-backed bearer tokens (`auth/*`, `users/*`).
- **Worker**: Celery task runner (`worker/tasks.py`).
- **Beat**: Celery scheduler (`worker/scheduler.py`) enqueueing periodic sync tasks.
- **Broker**: RabbitMQ (`RABBIT_MQ`) used by worker and beat, with a dedicated dead-letter exchange/queue path for failed task delivery.
- **Sync service**: orchestration (`sync/service.py`) with advisory lock (`sync/locking.py`).
- **External service**: upstream mock alerts endpoint consumed by `external_client/client.py`.
- **DB**: PostgreSQL via SQLAlchemy models/session (`db/*`), migrations in Alembic.
- **Health service**: status derivation (`health/service.py`) backed by `health/repository.py`.
- **Prometheus**: scrapes `/metrics` and provides external-call latency history to `/health`.

## Local runtime context

The default local deployment is a Docker Compose stack that boots:

- Nginx edge on `http://localhost:8000`
- FastAPI API container
- Celery worker container
- Celery beat container
- RabbitMQ broker
- PostgreSQL database
- Prometheus
- External mock alert source

The root `task setup` flow provisions local secrets, installs Python dependencies, generates local RabbitMQ TLS material, and starts the full stack.

## Edge exposure and auth model

The current edge and auth behavior is:

- Public edge endpoints: `POST /auth/login`, `POST /auth/logout`, `GET /alerts`, `POST /sync`, `GET /health`
- Internal API-only endpoints (not exposed by Nginx): `GET/PATCH /users/me`, `GET/PATCH/DELETE /users/{id}`, `/metrics`, `/ping`, `/docs`, `/redoc`, `/openapi.json`
- Business endpoints require database-backed bearer-token auth via `fastapi-users` (`Authorization: Bearer <token>`)
- External source auth is independent and uses `Authorization: Token <EXTERNAL_SERVICE_TOKEN>`
- Nginx rate limits `/auth/*` to `5` requests/minute per client IP with burst `3`, returning `429` when exceeded

## `/sync` manual execution

```mermaid
sequenceDiagram
    participant Client
    participant Nginx
    participant API as FastAPI /sync
    participant Auth as fastapi-users
    participant Sync as SyncService
    participant DB as PostgreSQL
    participant External as External Alerts API

    Client->>Nginx: POST /sync + Bearer token
    Nginx->>API: Proxy request
    API->>Auth: Validate active user from access token
    Auth-->>API: Authenticated user
    API->>Sync: sync_alerts()
    Sync->>DB: Begin transaction + advisory lock
    Sync->>DB: Read alerts_since checkpoint
    Sync->>External: GET /alerts/?since&up_to + Token auth
    External-->>Sync: Alerts payload
    Sync->>Sync: Enrich alerts
    Sync->>DB: Upsert alerts
    Sync->>DB: Insert worker_executions row
    Sync->>DB: Update checkpoint monotonically
    DB-->>Sync: Commit
    Sync-->>API: SyncResult
    API-->>Client: 201 Created + SyncResponse
```

### Notes

- `POST /sync` uses the same sync orchestration as worker-triggered executions.
- The sync window is based on the stored `alerts_since` checkpoint, or a fallback lookback derived from `SYNC_FREQUENCY_MINUTES`.
- Success writes alerts, checkpoint state, and a `worker_executions` record in one transaction.
- External failures are recorded as failed executions and returned as `502`; lock contention becomes `409`.

## Worker and scheduled executions

```mermaid
sequenceDiagram
    participant Beat as Celery Beat
    participant Broker as RabbitMQ
    participant Worker as Celery Worker
    participant Sync as SyncService
    participant DB as PostgreSQL
    participant External as External Alerts API

    Beat->>Broker: Publish alert_collector.sync_alerts on schedule
    Broker-->>Worker: Deliver task
    Worker->>Sync: sync_alerts(sync_run_id, attempt_number, retry_count)
    Sync->>DB: Begin transaction + advisory lock
    Sync->>DB: Read checkpoint
    Sync->>External: GET /alerts/?since&up_to
    alt Upstream succeeds
        External-->>Sync: Alerts payload
        Sync->>DB: Upsert alerts
        Sync->>DB: Insert successful worker_executions row
        Sync->>DB: Advance checkpoint
        DB-->>Worker: Commit
        Worker-->>Broker: Acknowledge task
    else Upstream fails or lock unavailable
        External-->>Sync: Error / timeout / invalid payload
        Sync->>DB: Insert failed worker_executions row
        DB-->>Worker: Commit failed attempt record
        Worker->>Broker: Retry same sync_run_id after 30s
    end
```

### Notes

- Beat schedules the task every `SYNC_FREQUENCY_MINUTES` using a crontab expression.
- Worker retries reuse the same `sync_run_id` and increment `attempt_number`.
- Health calculations later dedupe retries by keeping the latest attempt for each `sync_run_id`.

## Messaging topology and DLQ behavior

Celery messaging currently uses two RabbitMQ queues:

- Primary queue: `alert-collector`
- Dead-letter queue: `alert-collector.dlq`

The primary queue is declared with:

- `x-dead-letter-exchange=alert-collector.dlx`
- `x-dead-letter-routing-key=alert-collector.dead`

Dead-lettered messages are routed through `alert-collector.dlx` using routing key `alert-collector.dead` and land in `alert-collector.dlq`. For operational checks, validate queue arguments and queue depth with:

```bash
docker compose exec rabbitmq rabbitmqctl -p /alerts list_queues name arguments messages_ready messages_unacknowledged
docker compose exec rabbitmq rabbitmqctl -p /alerts list_exchanges name type
```

## `/alerts` retrieval

```mermaid
sequenceDiagram
    participant Client
    participant Nginx
    participant API as FastAPI /alerts
    participant Auth as fastapi-users
    participant Alerts as AlertsService
    participant DB as PostgreSQL

    Client->>Nginx: GET /alerts?since&up_to&severity&cursor&size + Bearer token
    Nginx->>API: Proxy request
    API->>Auth: Validate active user from access token
    Auth-->>API: Authenticated user
    API->>Alerts: list_alerts(filters, cursor params)
    Alerts->>DB: SELECT alerts with filters
    Note over Alerts,DB: Ordered by created_at DESC, id DESC
    DB-->>Alerts: Page of rows
    Alerts-->>API: Cursor page
    API-->>Client: AlertsCursorPage with alerts + next_page
```

### Notes

- Supported filters are `since`, `up_to`, and `severity`.
- Pagination is cursor-based through `fastapi-pagination`/`sqlakeyset`; page size is `1..200` and defaults to `50`.
- The API returns the page items under the `alerts` field alias.

## `/health` evaluation

```mermaid
sequenceDiagram
    participant Client
    participant Nginx
    participant API as FastAPI /health
    participant Auth as fastapi-users
    participant Health as HealthService
    participant Repo as HealthRepository
    participant DB as PostgreSQL
    participant Prometheus

    Client->>Nginx: GET /health + Bearer token
    Nginx->>API: Proxy request
    API->>Auth: Validate active user from access token
    Auth-->>API: Authenticated user
    API->>Health: evaluate()
    Health->>Repo: probe_database()
    Repo->>DB: SELECT 1
    DB-->>Repo: Probe result + latency
    Health->>Repo: list_recent_executions(3h)
    Repo->>DB: Read worker_executions rows
    DB-->>Repo: Recent execution history
    Health->>Repo: get_external_latency_p95_last_hour()
    Repo->>Prometheus: Query histogram_quantile over /metrics data
    Prometheus-->>Repo: p95 external latency
    Repo-->>Health: Probe + execution records + latency metric
    Health->>Health: Dedupe by sync_run_id and apply thresholds
    Health-->>API: HealthReport
    API-->>Client: status, DB health, last success, error rate, p95, recent errors
```

### Notes

- Status is derived from DB availability, a successful sync in the last 3 hours, last successful sync freshness, error rate, and p95 external latency from Prometheus.
- Retry attempts are deduped by taking the latest execution for each `sync_run_id`.
- `recent_errors` returns the most recent failed deduped executions.

## Configuration touchpoints

Settings are centralized in `alert-collector/src/alert_collector/settings.py`.

- Infra: `DATABASE_URL`, `RABBIT_MQ`, `RABBIT_MQ_TLS_CA_CERT`
- External ingest: `EXTERNAL_SERVICE_HOST`, `EXTERNAL_SERVICE_TOKEN`
- Scheduler/API: `SYNC_FREQUENCY_MINUTES`, `SERVICE_HOST`
- Optional health tuning: `PROMETHEUS_URL`, `HEALTH_RECENT_SUCCESS_HOURS`, `HEALTH_SUCCESS_STALE_MINUTES`, `HEALTH_ERROR_RATE_WARN`, `HEALTH_ERROR_RATE_DOWN`, `HEALTH_P95_WARN_SECONDS`, `HEALTH_P95_DOWN_SECONDS`
