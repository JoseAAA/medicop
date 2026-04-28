.PHONY: install setup up up-dev down down-volumes restart build logs logs-backend logs-frontend logs-qdrant pull-models seed health lint format type-check shell-backend shell-frontend shell-postgres

# ─── Bootstrap ───────────────────────────────────────────────────────────────

# Instalación end-to-end: claves auto-generadas + build + up + healthchecks + descarga del modelo.
# Único comando que el operador del hospital necesita correr.
install:
	@bash scripts/setup.sh
	@bash scripts/pull_models.sh

# Variante sin descarga del modelo (útil si quieres revisar antes de descargar 3 GB)
setup:
	@bash scripts/setup.sh

# ─── Docker ──────────────────────────────────────────────────────────────────

up:
	docker compose up -d

up-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

down:
	docker compose down

down-volumes:
	@echo "⚠️  Esto borrará todos los datos. Confirma con Ctrl+C para cancelar."
	@sleep 3
	docker compose down -v

restart:
	docker compose restart

build:
	docker compose build --no-cache

# ─── Logs ────────────────────────────────────────────────────────────────────

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

logs-qdrant:
	docker compose logs -f qdrant

# ─── Modelos y datos ─────────────────────────────────────────────────────────

pull-models:
	@bash scripts/pull_models.sh

# Re-siembra el médico demo + 6 pacientes + 10 guías. Idempotente: si los
# datos ya existen, no se duplican. Útil tras `make down-volumes`.
seed:
	@bash scripts/seed_database.sh

# ─── Tests ───────────────────────────────────────────────────────────────────
# Cuando agregues tests, créalos en backend/tests/ y descomenta el target.
# test:
# 	docker compose exec backend pytest tests/ -v

# ─── Calidad de código ───────────────────────────────────────────────────────

lint:
	docker compose exec backend ruff check app/
	docker compose exec frontend npm run lint

format:
	docker compose exec backend ruff format app/
	docker compose exec backend ruff check --fix app/

type-check:
	docker compose exec frontend npx tsc --noEmit

# ─── Salud ───────────────────────────────────────────────────────────────────

health:
	@bash scripts/healthcheck.sh

# ─── Shells ──────────────────────────────────────────────────────────────────

shell-backend:
	docker compose exec backend bash

shell-frontend:
	docker compose exec frontend sh

shell-postgres:
	docker compose exec postgres psql -U medicop medicop
