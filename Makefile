.PHONY: dev-api dev-web test lint build up down

dev-api:
	uv run uvicorn app.main:app --reload --port 8000

dev-web:
	cd web && pnpm dev

test:
	uv run pytest
	cd web && pnpm test

lint:
	uv run ruff check app tests
	cd web && pnpm lint

build:
	cd web && pnpm build

up:
	docker compose up --build

down:
	docker compose down
