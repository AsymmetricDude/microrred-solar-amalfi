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

**Alcance ampliado durante la ejecución:**
- `scripts/verify.sh`: el `verify` de una línea desde la raíz no descubre bien las pruebas
  (Django las busca desde el directorio actual); un script que entra a `proyecto_energia/` lo
  resuelve y deja un solo comando.
- `.python-version` (3.13) para que el intérprete sea reproducible.

## 4. Diseño / enfoque técnico
- Layout según ADR-0002. `manage.py` en `proyecto_energia/`; `pyproject` en la raíz.
- `uv init --bare` (o `--no-package`) para no generar un paquete instalable que no se usa.
- Versión de Django: la última 5.x que resuelva uv; se anota la exacta en la bitácora.
- `ALLOWED_HOSTS` = `["localhost", "127.0.0.1"]` en desarrollo.

## 5. Plan por fases
- [x] **Fase 1 —** Rama; `uv init`, `uv add django`, `uv add --dev ruff`; medir versiones.
- [x] **Fase 2 —** `startproject` + 3 × `startapp`; ajustar `settings.py`.
- [x] **Fase 3 —** Config de ruff, pruebas humo, `.gitignore` (`.venv/`, `db.sqlite3`, `__pycache__/`).
- [x] **Fase 4 —** `verify` en verde; validador; commit `chore(setup): …  Implements OT-0002`.

## 6. Criterios de aceptación
- [x] `manage.py check` → `System check identified no issues (0 silenced).`
- [x] `verify` completo en verde (salida pegada en la bitácora).
- [x] `uv.lock` versionado; `.venv` y `db.sqlite3` ignorados.

## 7. Checklist de cumplimiento
Sin `SECRET_KEY` real en el repo · Django 5.x · Python ≥ 3.11.

## 8. Riesgos y rollback
- **Riesgo:** Django 5.2 exige Python ≥ 3.10 — cumplido (3.13.14, fijado en `.python-version`).
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | **Medido:** `uv` resolvió Python **3.13.14** (gestionado por uv; el del sistema es 3.12.3) → fijado con `.python-version`. Django **5.2.18**, ruff **0.17.3**. Ambos cumplen `CLAUDE.md` (3.11+, Django 5.x). |
| 2026-10-28 | — | `settings.py`: `es-co`, `America/Bogota`, `USE_TZ=True`, 3 apps por `AppConfig`, `SECRET_KEY`/`DEBUG` desde entorno con valor de desarrollo fijo y no secreto, `ALLOWED_HOSTS` local. |
| 2026-10-28 | — | **`verify` en verde:** `All checks passed!` · `37 files already formatted` · `System check identified no issues (0 silenced).` · `No changes detected` · `Ran 4 tests … OK`. |
| 2026-10-28 | — | **Controles negativos** (`verify` debe fallar): (1) archivo con `import os` sin usar → exit 1 (ruff); (2) modelo sin `__str__` → exit 1 (ruff DJ008); (3) modelo correcto sin migración → `Migrations for 'monitoreo': + Create model Mutante`, exit 1. Restaurado → exit 0. |
| 2026-10-28 | — | **Validador (subagente, sólo lectura): ⚠️ aprobar con menores.** Reprodujo `verify` (exit 0), versiones, settings, `.gitignore` (`git check-ignore`) y el layout. Menores: (1) §8 decía 3.12.3 → corregido; (2) ADR-0002 no mencionaba la 3.13 de uv → añadido; (3) `models.py`/`admin.py` quedaron sin import tras `ruff --fix` → se reponen en OT-0003; (4) `uv.lock` versionado → se cumple con este commit; (5) docstring de plantilla en `urls.py` → cosmético, se deja. |
| 2026-10-28 | 0b97490 | **Cierre:** commit(s) de la OT; visto bueno del lead y merge *fast-forward* a `main`. (Las filas anteriores llevan «—» porque se escribieron antes del commit; el SHA de la OT es éste.) |
