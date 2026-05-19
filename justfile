set windows-shell := ["powershell.exe", "-c"]
set shell := ["sh", "-c"]
set dotenv-load
set dotenv-filename := "development.env"

default:
    just --list
js-build:
    bun run build
js-tests:
    bun test
js-tests-watch:
    bun test --watch
migrate-and-seed:
    python manage.py migrate
    python test_project/seed.py
run-doc-tests:
    mkdocs build --strict
run-coverage:
    python -m pytest django_glue/tests/ --cov=django_glue --cov-report=term-missing -v
run-server:
    python manage.py runserver
run-tests:
    python -m unittest discover -v ./tests
venv:
    uv venv .venv/
    uv pip install -e .[development,documentation]
