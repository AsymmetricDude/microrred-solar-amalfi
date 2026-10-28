# Órdenes de Trabajo (OT) — Microrred Solar ZNI (Amalfi, Antioquia)

> Cómo se planea, ejecuta y valida el trabajo en este proyecto. Es una versión **ligera**
> del arnés de OT de la bóveda (`Metodologia/Arnes_de_OT_con_Agentes`): mismo método,
> sin repo hub separado, sin GitHub Issues ni board. Las reglas del producto viven en
> [`CLAUDE.md`](../CLAUDE.md).

## Idea en una frase
Cada tarea es una **Orden de Trabajo (OT)**: un documento que dice *qué* hacer, *cómo* y
*cómo se valida*. Se diseña **antes** de tocar código y se ejecuta por fases.

| Concepto | Fuente de verdad | Dónde |
|---|---|---|
| Qué / cómo (el encargo) | La OT | `ordenes-de-trabajo/<tipo>/` |
| Estado | **La columna «Estado» del índice de abajo** (adaptación: no hay board) | Este archivo |
| Decisiones de arquitectura | ADR | [`docs/adr/`](../docs/adr/) |
| Historia y validación | git local (una rama por OT) + bitácora §9 de la OT | `git log` |

## Adaptaciones del arnés completo (decididas 2026-10-28)
- **Un solo repo, git local, sin remoto.** Se puede subir a GitHub después sin cambiar nada.
- **Estado en el índice**, no en un board: `Por hacer` → `En curso` → `En revisión` → `Hecho`.
- **Rama por OT** (`<tipo>/ot-####-slug`) y merge a `main` sólo con el visto bueno del lead.
- **Validador:** al cerrar cada OT, un subagente distinto del autor revisa el diff contra
  `CLAUDE.md` y la OT (sólo lectura). Su veredicto se anota en la bitácora.
- **Entorno:** `uv` (ver [ADR-0002](../docs/adr/ADR-0002-python-con-uv-y-layout.md)).

## Nomenclatura
- **ID global monotónico:** `OT-####`, nunca se reusa. Se cita en commits: `Implements OT-0004`.
- **Tipo = subcarpeta = prefijo de rama = tipo de commit:** `feat` `fix` `refactor` `chore` `docs`.
- **Archivo:** `<tipo>/OT-####-slug-corto.md`.

## Ciclo de vida
```
Lead aprueba el diseño de la OT (§4-§5)        → Estado: Por hacer
  → rama <tipo>/ot-####-slug, ejecución por fases → Estado: En curso
  → verify en verde + validador (subagente)      → Estado: En revisión
  → lead da el visto bueno → merge a main         → Estado: Hecho
```

## Regla de raíz: una OT resuelve el problema completo
1. La OT es dueña del **problema**, no de la tarea como se escribió. El objetivo (§2) es lo
   que se cumple; el alcance (§3) crece si hace falta.
2. Lo que tiene la **misma causa**, el **mismo síntoma** o **impide el objetivo** se corrige
   en la misma OT y se anota en §3 → «Alcance ampliado».
3. Un problema **distinto** abre otra OT, y lo decide el lead.

## Reglas de oro
- **Se diseña antes de codear.** Ninguna OT pasa a «En curso» sin que el lead apruebe §4-§5.
- **Se trabaja por partes:** una OT a la vez; al terminar cada una, se para y se reporta.
- **Evidencia medida, no afirmada:** cada cifra de la bitácora dice de qué comando salió.
- `verify` (abajo) en verde antes de pedir revisión.

## Comando `verify` (desde la raíz del repo)
```bash
uv run ruff check . && uv run ruff format --check . \
  && uv run python proyecto_energia/manage.py check \
  && uv run python proyecto_energia/manage.py makemigrations --check --dry-run \
  && uv run python proyecto_energia/manage.py test proyecto_energia
```
(Existe a partir de OT-0002; cada OT lo extiende con sus pruebas.)

## Índice de OT

| OT | Tipo | Título | Depende de | Estado |
|---|---|---|---|---|
| [OT-0001](chore/OT-0001-montar-arnes-ligero.md) | chore | Montar el arnés ligero de OT y definir el plan por fases | — | En revisión |
| [OT-0002](chore/OT-0002-inicializar-proyecto-django.md) | chore | Inicializar entorno uv, proyecto Django y 3 apps | OT-0001 | Por hacer |
| [OT-0003](feat/OT-0003-modelos-y-migraciones.md) | feat | Implementar los 5 modelos y sus migraciones | OT-0002 | Por hacer |
| [OT-0004](feat/OT-0004-generador-datos-sinteticos.md) | feat | Generador de datos sintéticos `seed_amalfi_data` | OT-0003 | Por hacer |
| [OT-0005](feat/OT-0005-api-dashboard-data.md) | feat | Vista del dashboard y endpoint `/api/dashboard-data/` | OT-0004 | Por hacer |
| [OT-0006](feat/OT-0006-frontend-seis-modulos.md) | feat | Frontend del dashboard: 6 módulos | OT-0005 | Por hacer |
| [OT-0007](chore/OT-0007-verificacion-integral-mvp.md) | chore | Verificación integral del MVP (consola, vistas, datos) | OT-0006 | Por hacer |
