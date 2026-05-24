set windows-shell := ["powershell.exe", "-c"]
set shell := ["sh", "-c"]
set dotenv-load := true
set dotenv-filename := "development.env"

export PYTHONPATH := if os() == "linux" { env_var_or_default("PYTHONPATH_APPEND", "") + ":." } else { env_var_or_default("PYTHONPATH_APPEND", "") + ";." }
PYTHON := if os() == "linux" { ".venv/bin/python" } else { ".venv/Scripts/python.exe" }

default:
    just --list

js-build:
    bun run build

js-tests:
    bun test

js-coverage:
    bun test --coverage

js-tests-watch:
    bun test --watch

migrate-and-seed:
    {{ PYTHON }} manage.py migrate
    {{ PYTHON }} seed.py

opencode:
    ./.venv/Scripts/activate.bat
    opencode

run-doc-tests:
    mkdocs build --strict

run-coverage:
    {{ PYTHON }} -m pytest django_glue/tests/ --cov=django_glue --cov-report=term-missing -v

run-server:
    {{ PYTHON }} manage.py runserver

run-tests:
    {{ PYTHON }} -m pytest django_glue/tests/ -v

lock:
    bun install
    uv lock

venv:
    uv venv .venv/
    uv pip install -e .[development,documentation]
