---
id: OT-0002
tipo: chore
titulo: "Inicializar entorno uv, proyecto Django y las 3 apps"
rama: "chore/ot-0002-inicializar-proyecto"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: [OT-0001]
docs_ref: [CLAUDE.md, docs/adr/ADR-0002-python-con-uv-y-layout.md]
creado: 2026-10-28
---

# OT-0002 — Inicializar entorno uv, proyecto Django y las 3 apps

## 1. Contexto y problema
No existe entorno ni proyecto. Todo lo demás (modelos, seed, API, UI) cuelga de esto.

## 2. Objetivo
`uv run python proyecto_energia/manage.py check` termina sin errores con las apps
`monitoreo`, `analitica` y `financiero` registradas, idioma `es-co` y zona `America/Bogota`,
y el comando `verify` del índice corre en verde.

## 3. Alcance
**Qué SÍ entra:**
- `uv init` (sin paquete), `pyproject.toml` con `django>=5.1,<6` y `ruff` (dev), `uv.lock`, `.venv/`.
- `django-admin startproject proyecto_energia` y `startapp` × 3 dentro de `proyecto_energia/`.
- `settings.py`: `LANGUAGE_CODE="es-co"`, `TIME_ZONE="America/Bogota"`, `USE_TZ=True`,
  `USE_I18N=True`, apps registradas, `TEMPLATES` con `APP_DIRS=True`.
- `SECRET_KEY` y `DEBUG` leídos de variables de entorno con valores de desarrollo por
  defecto (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`), para no dejar un secreto real en el repo.
- Configuración de `ruff` en `pyproject.toml` (excluye `migrations/`).
- Una prueba humo por app (que la app esté instalada) para que `manage.py test` tenga algo
  que correr desde el día uno.

**Qué NO entra:** modelos (OT-0003), URLs del dashboard (OT-0005).

**Alcance ampliado durante la ejecución:** _(vacío)_

## 4. Diseño / enfoque técnico
- Layout según ADR-0002. `manage.py` en `proyecto_energia/`; `pyproject` en la raíz.
- `uv init --bare` (o `--no-package`) para no generar un paquete instalable que no se usa.
- Versión de Django: la última 5.x que resuelva uv; se anota la exacta en la bitácora.
- `ALLOWED_HOSTS` = `["localhost", "127.0.0.1"]` en desarrollo.

## 5. Plan por fases
- [ ] **Fase 1 —** Rama; `uv init`, `uv add django`, `uv add --dev ruff`; medir versiones.
- [ ] **Fase 2 —** `startproject` + 3 × `startapp`; ajustar `settings.py`.
- [ ] **Fase 3 —** Config de ruff, pruebas humo, `.gitignore` (`.venv/`, `db.sqlite3`, `__pycache__/`).
- [ ] **Fase 4 —** `verify` en verde; validador; commit `chore(setup): …  Implements OT-0002`.

## 6. Criterios de aceptación
- [ ] `manage.py check` → `System check identified no issues (0 silenced).`
- [ ] `verify` completo en verde (salida pegada en la bitácora).
- [ ] `uv.lock` versionado; `.venv` y `db.sqlite3` ignorados.

## 7. Checklist de cumplimiento
Sin `SECRET_KEY` real en el repo · Django 5.x · Python ≥ 3.11.

## 8. Riesgos y rollback
- **Riesgo:** Django 5.2 exige Python ≥ 3.10 — cumplido (3.12.3).
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
