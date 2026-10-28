---
id: OT-0003
tipo: feat
titulo: "Implementar los 5 modelos y sus migraciones"
rama: "feat/ot-0003-modelos"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: [OT-0002]
docs_ref: [CLAUDE.md §4]
creado: 2026-10-28
---

# OT-0003 — Implementar los 5 modelos y sus migraciones

## 1. Contexto y problema
`CLAUDE.md` §4 fija el esquema de 5 modelos en 3 apps. Sin él no hay dónde sembrar datos.

## 2. Objetivo
Los 5 modelos existen **con los nombres de campo exactos** de `CLAUDE.md`, sus migraciones
aplican desde una base vacía y `makemigrations --check` no detecta cambios pendientes.

## 3. Alcance
**Qué SÍ entra:**
- `monitoreo.RegistroSistema`, `monitoreo.ConsumoPorSegmento`,
  `analitica.PrediccionYAnomalia`, `financiero.ResumenFinanciero`, `financiero.FlujoCajaAnual`.
- `TextChoices` para `estado_sistema` y `tipo_usuario`.
- `Meta.ordering`, `__str__`, `verbose_name` en español.
- Registro en el admin de Django (útil para revisar datos durante el trabajo de grado).
- Pruebas de modelo: unicidad de `timestamp` y de `anio`, `related_name` correctos.

**Qué NO entra:** datos (OT-0004), validaciones de rango físico en el modelo (las garantiza el
generador y sus pruebas).

**Alcance ampliado durante la ejecución:**
- `pyproject.toml`: `src = ["proyecto_energia"]` en ruff. Sin esto, isort trataba las apps
  como paquetes de terceros y exigía un orden de imports erróneo en cuanto una app importó a otra.
- Prueba de esquema `EsquemaSegunClaudeMdTests`: compara los nombres de campo de los 5 modelos
  con `CLAUDE.md` §4, para que un renombrado futuro no pase en silencio.

## 4. Diseño / enfoque técnico
| Modelo | Campos (exactos de `CLAUDE.md`) | Decisiones extra |
|---|---|---|
| `RegistroSistema` | `timestamp` (unique, db_index) · `irradiancia_wm2` · `temp_ambiente_c` · `temp_panel_c` · `generacion_fv_kwh` · `demanda_total_kwh` · `soc_porcentaje` · `autonomia_horas` · `potencia_bateria_kw` · `estado_sistema` | `EstadoSistema(TextChoices)`: `OPTIMO`, `ALERTA`, `CRITICO`; `max_length=10`; `ordering=["timestamp"]` |
| `ConsumoPorSegmento` | FK `registro` → `RegistroSistema` (`related_name="segmentos"`, `CASCADE`) · `tipo_usuario` · `consumo_kwh` | `UniqueConstraint(registro, tipo_usuario)`: un valor por segmento y hora; **sin `ordering` por defecto** (evita un JOIN implícito; el orden va en el admin y en consultas explícitas) |
| `PrediccionYAnomalia` | O2O `registro` → `RegistroSistema` (`related_name="analitica"`, `CASCADE`) · `generacion_predicha_kwh` · `demanda_predicha_kwh` · `es_anomalia` (default False, **db_index**) · `tipo_anomalia` · `descripcion_anomalia` | `db_index` en `es_anomalia` porque la API filtra por él; **sin `ordering` por defecto** (ídem) |
| `ResumenFinanciero` | `capex_cop` · `opex_anual_cop` · `vpn_cop` · `tir_porcentaje` · `lcoe_cop_kwh` · `ahorro_anual_diesel_cop` · `toneladas_co2_evitadas_anual` | «Registro único»: lo garantiza el seed (borra y crea uno) + método de clase `actual()`; sin singleton mágico |
| `FlujoCajaAnual` | `anio` (unique) · `ingresos_ahorro_cop` · `costos_om_cop` · `flujo_neto_cop` · `flujo_acumulado_cop` | `ordering=["anio"]` |

- **Nombre de la FK/O2O:** `registro` en ambos — **aprobado por el lead (2026-10-28)**.
- **Dinero en `BigIntegerField`** (pesos enteros) como pide `CLAUDE.md`; `lcoe_cop_kwh` y
  `tir_porcentaje` son `FloatField` por especificación.
- Migraciones generadas por Django, sin editar a mano.
- `tipo_anomalia`/`descripcion_anomalia` con `null=True` como pide `CLAUDE.md`, aunque ruff
  (DJ001) lo desaconseja: se silencia **sólo en esas dos líneas**, con el porqué en un comentario.

## 5. Plan por fases
- [x] **Fase 1 —** Modelos de `monitoreo` + admin.
- [x] **Fase 2 —** Modelo de `analitica` + admin.
- [x] **Fase 3 —** Modelos de `financiero` + admin.
- [x] **Fase 4 —** `makemigrations`, `migrate` sobre base vacía, pruebas de modelo.
- [x] **Fase 5 —** `verify`, validador, commit.

## 6. Criterios de aceptación
- [x] `migrate` desde base vacía sin errores (salida en bitácora).
- [x] `makemigrations --check --dry-run` → `No changes detected`.
- [x] Campos comparados uno a uno contra `CLAUDE.md` — automatizado en `EsquemaSegunClaudeMdTests` (la lista vive en la prueba, no en la bitácora, para que no se desincronice).
- [x] `verify` en verde.

## 7. Checklist de cumplimiento
Nombres exactos de `CLAUDE.md` · ORM portable a PostgreSQL (nada específico de SQLite).

## 8. Riesgos y rollback
- **Resuelto (2026-10-28):** FK/O2O se llaman `registro`.
- **Rollback:** borrar la rama y `db.sqlite3`.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | **`migrate` desde base vacía (medido, `rm db.sqlite3`):** `monitoreo.0001_initial… OK`, `analitica.0001_initial… OK`, `financiero.0001_initial… OK`. |
| 2026-10-28 | — | **SQL (`sqlmigrate`):** `timestamp … UNIQUE`; `CONSTRAINT "un_consumo_por_segmento_y_hora" UNIQUE ("registro_id","tipo_usuario")`; `registro_id … UNIQUE` en la O2O; `CREATE INDEX … ("es_anomalia")`. Dinero en `bigint`/`real` según `CLAUDE.md`; nada específico de SQLite. |
| 2026-10-28 | — | **`verify`:** `All checks passed!` · `No changes detected` · `Ran 18 tests … OK` (4 humo + 14 de modelo: unicidad de `timestamp`/`anio`, un segmento por hora, una predicción por registro, `related_name`, cascada, `actual()`, BigInteger de 64 bits, orden). |
| 2026-10-28 | — | **Control negativo de la prueba de esquema:** renombrar `temp_ambiente_c` → `temp_amb_c` ⇒ `FAIL … modelo='RegistroSistema'` con los dos nombres. (El primer intento, con `soc_porcentaje`, lo detuvo antes el check del admin E108 — falla, pero no mide la prueba; por eso se repitió con un campo fuera del admin.) Restaurado → verde. |
| 2026-10-28 | — | **Validador (subagente, sólo lectura): ⚠️ aprobar con menores, nada bloquea.** Confirmó campo por campo contra `CLAUDE.md` §4, DDL portable, `max_length` suficientes (11/12 en choices; `CONSUMO_NOCTURNO_ATIPICO` 24/40) y que los `noqa` están acotados. Menores atendidos: (1) `__str__` mostraba UTC (12:00 Bogotá → «17:00») → `timezone.localtime`; (2) `__str__` fallaba en instancias sin guardar → guardas; (3) `ordering` por `registro__timestamp` metía un JOIN en toda consulta (incluida la de anomalías de OT-0005) → se quita del modelo y va al `ModelAdmin`; (4) la prueba de esquema sólo comparaba nombres → ahora nombre **y tipo**, más `related_name`. Las migraciones 0001 (aún sin commit) se regeneraron en vez de añadir una 0002 de `Meta`. |
| 2026-10-28 | — | **Tras las correcciones:** `verify` → `No changes detected` · `Ran 21 tests … OK`. Control negativo de tipos: `vpn_cop` `BigIntegerField`→`IntegerField` ⇒ `FAIL … modelo='ResumenFinanciero'`; restaurado → OK. |
