.PHONY: up down build logs migrate makemigrations shell test seed backend-shell frontend-dev

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

shell:
	docker compose exec backend python manage.py shell

backend-shell:
	docker compose exec backend sh

test:
	docker compose exec backend pytest

seed:
	docker compose exec backend python manage.py seed_demo_data

frontend-dev:
	cd frontend && npm run dev
