# fiofio

`fiofio` is centered on the `alert-collector` service: a FastAPI API plus Celery worker/beat stack that periodically pulls alerts from a mocked upstream API, enriches and stores them in PostgreSQL, and exposes authenticated endpoints for listing alerts, triggering syncs, and checking overall system health.

## Base Requirements

- Python `3.13`
- `uv`
- [`task`](https://taskfile.dev/)
- Docker with Docker Compose
- `openssl` (used by local RabbitMQ TLS bootstrap)

## First Setup

From the repository root, run:

```sh
task setup
```

The command handles:

- creating local secret files and `.env`
    - Note: Local secret files are meant to be a placeholder for a proper secrets manager
- installs Python dependencies for `alert-collector` and `externalMock`
- generates RabbitMQ development certificates
- builds and starts the Docker Compose stack

## First Useful Commands

Create an API user, along with a bearer token:

```sh
task get-user-and-token EMAIL=admin@example.com PASSWORD=change-me
```
Note: can be split into `create-user` and `get-token`.

Run formatting and tests:

```sh
task fmt
task test
```

## Further Reading

- Architecture overview: see [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- Development decisions and API exposure notes: see [`DECISIONS.md`](./DECISIONS.md)

Inspect the local stack:

```sh
task logs SERVICE=alert-collector-api
```

# HOW TO

Test the service locally with this flow:

1. Bootstrap the stack:

```sh
task setup
```

2. Create a user and retrieve a bearer token:

```sh
task get-user-and-token EMAIL=admin@example.com PASSWORD=change-me
```

3. Use `POST /sync` to trigger a manual sync run.
4. Use `GET /alerts` to inspect collected alerts.
5. Use `GET /health` to monitor overall system health.
6. Use `task db-worker-executions` to get a summary of recent worker runs.

To measure how the service behaves when the external system is unreliable, adjust `MOCK_ERROR_PROBABILITY` in `.env` before running the stack or restarting the affected services.

## Local Endpoints

The Nginx edge service publishes the collector on `http://localhost:8000`.

- `POST /auth/login`
- `POST /auth/logout`
- `GET /alerts`
- `POST /sync`
- `GET /health`

All business endpoints require a bearer token. See `DECISIONS.md` for the current public/private endpoint split and auth details.
