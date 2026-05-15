set windows-shell := ["powershell.exe", "-c"]
set shell := ["sh", "-c"]
set dotenv-load
set dotenv-filename := "development.env"

default:
	just --list

build-js:
	bun run build

migrate-and-seed:
	python manage.py migrate
	python test_project/seed.py

run-server:
	python manage.py runserver

run-tests:
	python -m unittest discover -v ./tests

run-doc-tests:
	mkdocs build --strict

run-coverage:
	python -m pytest django_glue/tests/ --cov=django_glue --cov-report=term-missing -v

venv:
	uv venv .venv/
	uv pip install -e .[development,documentation]


