.PHONY: help install dev migrate seed test lint

help:
	@echo "AutomIQ Backend — Comandos disponíveis:"
	@echo "  make install   - Instalar dependências"
	@echo "  make dev       - Rodar servidor em modo desenvolvimento"
	@echo "  make migrate   - Gerar e aplicar migrations"
	@echo "  make seed      - Popular banco com dados iniciais"
	@echo "  make test      - Rodar testes"
	@echo "  make lint      - Verificar código"
	@echo "  make docker-up - Subir stack completa via Docker Compose"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate-generate:
	alembic revision --autogenerate -m "$(msg)"

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

seed:
	python scripts/seed.py

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

lint:
	python -m py_compile app/**/*.py
	echo "Syntax OK"

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

create-db:
	python -c "from db.session import engine; from db.base import Base; Base.metadata.create_all(bind=engine); print('Tables created!')"

reset-db:
	alembic downgrade base
	alembic upgrade head
	python scripts/seed.py
