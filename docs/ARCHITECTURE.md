# Alert Collector Architecture

This document maps the current `alert-collector` implementation to the planned architecture and shows component interactions for the three primary use cases: `sync`, `alerts`, and `health`.

## Components

- **API**: FastAPI app (`api/app.py`) exposing `/sync`, `/alerts`, `/health`.
- **Worker**: Celery task runner (`worker/tasks.py`).
- **Beat**: Celery scheduler (`worker/scheduler.py`) enqueueing periodic sync tasks.
- **Broker**: RabbitMQ (`RABBIT_MQ`) used by worker and beat.
- **Sync Service**: orchestration (`sync/service.py`) with advisory lock (`sync/locking.py`).
- **External Service**: upstream alerts endpoint consumed by `external_client/client.py`.
- **DB**: PostgreSQL via SQLAlchemy models/session (`db/*`), migrations in Alembic.
- **Health Service**: status derivation (`health/service.py`) backed by repository (`health/repository.py`).

## Sync use case

### Interaction diagram

```mermaid
flowchart LR
  Beat[Celery Beat] -->|schedule sync task| Broker[(RabbitMQ)]
  Broker -->|deliver task| Worker[Celery Worker]
  API[FastAPI POST /sync] -->|invoke sync_alerts| SyncService[SyncService]
  Worker -->|invoke same sync_alerts| SyncService

  SyncService -->|acquire lock| Lock[Postgres advisory lock]
  SyncService -->|read/update alerts_since checkpoint| KV[(KeyValueState)]
  SyncService -->|GET /alerts?since&up_to| External[External Service]
  SyncService -->|enrich and upsert alerts| Alerts[(alerts table)]
  SyncService -->|record success/failure attempt| Exec[(worker_executions table)]
```

### Flow notes

- `POST /sync` and `sync_alerts_task` share the same orchestration path.
- Sync execution is guarded by a transaction-scoped advisory lock.
- Alerts, worker execution record, and checkpoint changes are committed atomically.
- On ingestion failure, a failed execution is stored and checkpoint does not advance.

## Alerts use case

### Interaction diagram

```mermaid
flowchart LR
  Client[Client] -->|GET /alerts with filters + cursor| API[FastAPI /alerts]
  API -->|decode/validate cursor continuity| Cursor[Pagination helpers]
  API -->|query alerts ordered by created_at DESC, id DESC| DB[(alerts table)]
  DB -->|page rows| API
  API -->|encode next cursor + links| Cursor
  API -->|AlertsPageResponse| Client
```

### Flow notes

- Filters are `since`, `up_to`, `severity`; pagination uses `cursor` + `limit`.
- Cursor continuity rejects mismatched filter reuse for stable paging semantics.
- Canonical ordering is descending by `created_at`, then `id`.

## Health use case

### Interaction diagram

```mermaid
flowchart LR
  Client[Client] -->|GET /health| API[FastAPI /health]
  API -->|evaluate| HealthSvc[HealthService]
  HealthSvc -->|probe SELECT 1 + latency| Repo[HealthRepository]
  HealthSvc -->|fetch recent executions 12h| Repo
  Repo -->|read worker_executions| Exec[(worker_executions table)]
  Repo -->|database probe status| DB[(PostgreSQL)]
  HealthSvc -->|dedupe by sync_run_id + threshold rules| API
  API -->|HealthResponse status + diagnostics| Client
```

### Flow notes

- Health status combines DB availability, success staleness, error-rate, and p95 latency.
- Retry attempts are deduped by taking the latest attempt per `sync_run_id`.
- Output includes DB probe fields, last successful sync, rates/latency, and recent errors.

## Configuration touchpoints

Settings are centralized in `alert-collector/src/alert_collector/settings.py`.

- Infra: `DATABASE_URL`, `RABBIT_MQ`.
- External ingest: `EXTERNAL_SERVICE_HOST`, `EXTERNAL_SERVICE_TOKEN`.
- Scheduler/API: `SYNC_FREQUENCY_MINUTES`, `SERVICE_HOST`.
- Optional behavior tuning: `SYNC_BOOTSTRAP_LOOKBACK_MINUTES` and health threshold env vars.
