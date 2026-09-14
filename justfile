set windows-shell := ["powershell.exe", "-c"]
set dotenv-load
set dotenv-filename := "development.env"

export PYTHONPATH := if os() == "linux" { env_var_or_default('PYTHONPATH_APPEND', '') + ':.'} else { env_var_or_default('PYTHONPATH_APPEND', '') + ';.' }

PYTHON := if os() == "linux" { ".venv/bin/python" } else { ".venv/Scripts/python.exe" }
E2E_ENV := if os() == "linux" { "DJANGO_GLUE_RUN_E2E=1 " } else { "$env:DJANGO_GLUE_RUN_E2E='1'; " }

default:
	just --list

make-migrations:
	{{PYTHON}} ./manage.py makemigrations

migrate:
	{{PYTHON}} ./manage.py migrate

python *ARGS:
	{{PYTHON}} "{{ARGS}}"

run-server:
	{{PYTHON}} ./manage.py runserver

shell:
	{{PYTHON}} ./manage.py shell

run-worker:
	{{PYTHON}} ./worker.py

docs:
	{{PYTHON}} -m mkdocs build --strict

test-app *PATTERN:
	{{PYTHON}} -m pytest {{PATTERN}}

test:
	{{PYTHON}} -m pytest -m "not e2e" .

test-failed:
	{{PYTHON}} -m pytest . --ff --lf

test-coverage:
	{{PYTHON}} -m pytest . --cov=django_glue --cov-report=term-missing --cov-report=html:.test_coverage/

test-e2e *ARGS:
	{{E2E_ENV}}{{PYTHON}} -m pytest -m e2e {{ARGS}}

test-e2e-headed *ARGS:
	{{E2E_ENV}}{{PYTHON}} -m pytest -m e2e --headed --slowmo 1000 {{ARGS}}

demo NAME="" SPEED="normal":
	{{E2E_ENV}}{{ if os() == "linux" { "DEMO_MODE=narrate DEMO_SPEED=" + SPEED + " " } else { "$env:DEMO_MODE='narrate'; $env:DEMO_SPEED='" + SPEED + "'; " } }}{{PYTHON}} -m pytest -m e2e --headed --video on {{ if NAME == "" { "" } else { "-k '" + replace(NAME, "-", "_") + "'" } }}

demos:
	{{PYTHON}} -m pytest -m e2e --collect-only -q

act *ARGS:
	act {{ARGS}}
