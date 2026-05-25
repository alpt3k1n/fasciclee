.PHONY: up up-prod down migrate migrate-create shell-api shell-db logs fe-dev fe-build gpu-worker deploy setup

up:
	docker compose up -d

up-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

down:
	docker compose down

migrate:
	docker compose exec api alembic upgrade head

migrate-create:
	docker compose exec api alembic revision -m "$(msg)"

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U $$PG_USER fasikul

logs:
	docker compose logs -f --tail=100 api worker_vps

logs-all:
	docker compose logs -f --tail=50

fe-dev:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

gpu-worker:
	@bash scripts/start_gpu_worker.sh

deploy:
	@bash scripts/deploy.sh

setup:
	@bash scripts/setup.sh
