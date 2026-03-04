set windows-shell := ["powershell.exe", "-c"]
set shell := ["sh", "-c"]
set dotenv-load
set dotenv-filename := "development.env"

default:
	just --list

build-venv:
	uv venv .venv/
	uv pip install -e .[development,documentation]

migrate-and-seed:
	python manage.py migrate
	python test_project/seed.py

run-server:
	python manage.py runserver

run-tests:
	python -m unittest discover -v ./tests

run-doc-tests:
	mkdocs build --strict
