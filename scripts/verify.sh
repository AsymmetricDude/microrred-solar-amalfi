#!/usr/bin/env bash
# Comando `verify` del proyecto (ver ordenes-de-trabajo/00-README.md).
# Se corre desde cualquier lugar; falla en el primer paso que no pase.
set -euo pipefail

raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$raiz"

uv run ruff check .
uv run ruff format --check .

cd proyecto_energia
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test
