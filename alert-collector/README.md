# Alert Collector

## Dead-letter queue (DLQ)

Celery now declares two RabbitMQ queues:

- `alert-collector` (primary queue)
- `alert-collector.dlq` (dead-letter queue)

The primary queue is configured with:

- `x-dead-letter-exchange=alert-collector.dlx`
- `x-dead-letter-routing-key=alert-collector.dead`

### Inspect DLQ wiring and depth

Run from the repository root:

```bash
docker compose exec rabbitmq rabbitmqctl -p /alerts list_queues name arguments messages_ready messages_unacknowledged
docker compose exec rabbitmq rabbitmqctl -p /alerts list_exchanges name type
```

You should see:

- `alert-collector` with dead-letter arguments
- `alert-collector.dlq` bound to `alert-collector.dlx` using `alert-collector.dead`

### Optional UI check

If you expose RabbitMQ management (`15672:15672`) in `docker-compose.yml`, you can inspect exchanges/queues in the UI at <http://localhost:15672>.
