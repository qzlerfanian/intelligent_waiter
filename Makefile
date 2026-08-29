.PHONY: up down build migrate test lint prod-check load-test backup

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose run --rm api python manage.py migrate

test:
	docker compose run --rm api pytest
	docker compose run --rm web npm test -- --run

lint:
	docker compose run --rm api ruff check .
	docker compose run --rm web npm run lint

prod-check:
	docker compose -f compose.yaml -f compose.production.yaml config --quiet
	docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.production api python manage.py check --deploy

load-test:
	docker run --rm -i --network host -e BASE_URL=http://localhost:8000/api/v1 grafana/k6 run - < load-tests/smoke.js

backup:
	docker compose exec -T db sh -c 'pg_dump --format=custom --no-owner --no-acl -U $$POSTGRES_USER $$POSTGRES_DB' > baran-backup.dump
