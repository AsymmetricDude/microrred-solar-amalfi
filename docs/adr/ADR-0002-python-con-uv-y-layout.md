---
id: ADR-0002
titulo: "Python con uv y layout del repositorio"
estado: aceptada
fecha: 2026-10-28
supersede: ""
tags: [adr, decision, entorno, estructura]
---

# ADR-0002 — Python con uv y layout del repositorio

## Contexto

- `CLAUDE.md` pide Python 3.11+ y Django 5.x.
- **Medido (2026-10-28, WSL):** Python 3.12.3 del sistema, `uv 0.11.32`, `git` disponible.
- El lead eligió `uv` (igual que en otros proyectos propios) y git local sin remoto.

## Decisión

- **Entorno:** `uv` gestiona `.venv/`, `pyproject.toml` y `uv.lock` en la raíz del repo.
  `requires-python = ">=3.11"`. Todo comando se corre con `uv run`.
- **Dependencias:** `django>=5.1,<6` en runtime; `ruff` como dependencia de desarrollo.
  Nada más mientras no haga falta (sin numpy/pandas: el generador usa `random` y `math`).
- **Layout:**
  ```text
  sun_ia/                      ← raíz del repo (git, pyproject, uv.lock, CLAUDE.md)
  ├── ordenes-de-trabajo/      ← OT (arnés ligero)
  ├── docs/adr/                ← decisiones
  └── proyecto_energia/        ← proyecto Django (manage.py)
      ├── proyecto_energia/    ← settings, urls, wsgi
      ├── monitoreo/           ← app core + dashboard + seed_amalfi_data
      ├── analitica/
      └── financiero/
  ```
- `db.sqlite3` **no** se versiona: se regenera con `migrate` + `seed_amalfi_data`.

## Consecuencias
- Quien clone el repo necesita `uv` (`uv sync` crea el entorno). Si el trabajo de grado
  exige `requirements.txt`, se exporta con `uv export --format requirements-txt`.
