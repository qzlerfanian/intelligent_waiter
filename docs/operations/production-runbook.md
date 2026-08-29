# Production runbook

- Deploy with `docker compose -f compose.yaml -f compose.production.yaml up -d --build` using a secret-managed env file; never use `.env.example` credentials.
- Liveness: `/api/v1/health/`; readiness: `/api/v1/ready/`; Prometheus text metrics: `/api/v1/metrics/` with `Authorization: Bearer $METRICS_TOKEN`.
- Run migrations as a release job before shifting traffic: `python manage.py migrate --noinput`, then `python manage.py check --deploy`.
- Back up PostgreSQL with `scripts/backup.sh`. Restore drills must be performed on an isolated database with `scripts/restore.sh`; verify order, payment, invoice, and tenant counts afterward.
- Alert on readiness failures, HTTP 5xx, p95 latency, failed/pending Outbox growth, worker absence, Redis memory pressure, database connections, storage, and backup age.
- Scale API and workers independently. Run exactly one Beat scheduler. Keep PostgreSQL and Redis private and encrypted in transit at the infrastructure layer.
- Rotate `APP_SECRET_KEY`, database credentials, OpenAI key and metrics token through the platform secret manager. Rotation of `APP_SECRET_KEY` invalidates sessions/JWT signatures and requires a coordinated rollout.
- Roll back application images first. Never reverse a destructive migration until a verified database snapshot exists.
