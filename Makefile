PYTHON ?= python3
UVICORN ?= uvicorn

.PHONY: install run migrate compose-up compose-down format lint test

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8004 --reload

migrate:
	alembic upgrade head

compose-up:
	docker compose up --build

compose-down:
	docker compose down

format:
	$(PYTHON) -m ruff format app

lint:
	$(PYTHON) -m ruff check app

test:
	$(PYTHON) -m pytest
