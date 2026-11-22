.PHONY: dev-api dev-web dev-worker dev-beat migrate test test-postgres lint build up down

dev-api:
	uv run uvicorn app.main:app --reload --port 8000

dev-web:
	cd web && pnpm dev

dev-worker:
	uv run celery -A app.workers.celery_app:celery_app worker --loglevel=INFO --concurrency=1

dev-beat:
	uv run celery -A app.workers.celery_app:celery_app beat --loglevel=INFO

migrate:
	uv run alembic upgrade head

test:
	uv run pytest
	cd web && pnpm test

test-postgres:
	docker compose up -d db
	docker compose exec -T db dropdb --if-exists -U policyrag policyrag_test
	docker compose exec -T db createdb -U policyrag policyrag_test
	TEST_DATABASE_URL=postgresql+asyncpg://policyrag:policyrag@127.0.0.1:5432/policyrag_test \
	EMBEDDING_PROVIDER=hash EMBEDDING_DIMENSIONS=1024 HASH_EMBEDDING_DIMENSIONS=1024 \
	uv run pytest tests/test_store_contract.py -q
	-docker compose exec -T db dropdb -U policyrag policyrag_test

lint:
	uv run ruff check app tests
	cd web && pnpm lint

build:
	cd web && pnpm build

up:
	docker compose up --build

down:
	docker compose down
