.PHONY: up down migrate migrate-create shell-api shell-db logs fe-dev fe-build gpu-worker setup

up:
	docker compose up -d

down:
	docker compose down

migrate:
	docker compose exec api alembic upgrade head

migrate-create:
	docker compose exec api alembic revision --autogenerate -m "$(msg)"

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U $$PG_USER fasikul

logs:
	docker compose logs -f api worker_vps

fe-dev:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

gpu-worker:
	@bash scripts/start_gpu_worker.sh

setup: up
	@echo "Waiting 15s for services to start..."
	@sleep 15
	$(MAKE) migrate
	@echo "Done!"
