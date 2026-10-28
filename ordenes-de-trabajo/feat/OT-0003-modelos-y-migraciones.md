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

**Alcance ampliado durante la ejecución:** _(vacío)_

## 4. Diseño / enfoque técnico
| Modelo | Campos (exactos de `CLAUDE.md`) | Decisiones extra |
|---|---|---|
| `RegistroSistema` | `timestamp` (unique, db_index) · `irradiancia_wm2` · `temp_ambiente_c` · `temp_panel_c` · `generacion_fv_kwh` · `demanda_total_kwh` · `soc_porcentaje` · `autonomia_horas` · `potencia_bateria_kw` · `estado_sistema` | `EstadoSistema(TextChoices)`: `OPTIMO`, `ALERTA`, `CRITICO`; `max_length=10`; `ordering=["timestamp"]` |
| `ConsumoPorSegmento` | FK `registro` → `RegistroSistema` (`related_name="segmentos"`, `CASCADE`) · `tipo_usuario` · `consumo_kwh` | `UniqueConstraint(registro, tipo_usuario)`: un valor por segmento y hora |
| `PrediccionYAnomalia` | O2O `registro` → `RegistroSistema` (`related_name="analitica"`, `CASCADE`) · `generacion_predicha_kwh` · `demanda_predicha_kwh` · `es_anomalia` (default False, **db_index**) · `tipo_anomalia` · `descripcion_anomalia` | `db_index` en `es_anomalia` porque la API filtra por él |
| `ResumenFinanciero` | `capex_cop` · `opex_anual_cop` · `vpn_cop` · `tir_porcentaje` · `lcoe_cop_kwh` · `ahorro_anual_diesel_cop` · `toneladas_co2_evitadas_anual` | «Registro único»: lo garantiza el seed (borra y crea uno) + método de clase `actual()`; sin singleton mágico |
| `FlujoCajaAnual` | `anio` (unique) · `ingresos_ahorro_cop` · `costos_om_cop` · `flujo_neto_cop` · `flujo_acumulado_cop` | `ordering=["anio"]` |

- **Nombre de la FK:** `CLAUDE.md` no lo da; se propone `registro` en ambos (pregunta abierta §8).
- **Dinero en `BigIntegerField`** (pesos enteros) como pide `CLAUDE.md`; `lcoe_cop_kwh` y
  `tir_porcentaje` son `FloatField` por especificación.
- Migraciones generadas por Django, sin editar a mano.

## 5. Plan por fases
- [ ] **Fase 1 —** Modelos de `monitoreo` + admin.
- [ ] **Fase 2 —** Modelo de `analitica` + admin.
- [ ] **Fase 3 —** Modelos de `financiero` + admin.
- [ ] **Fase 4 —** `makemigrations`, `migrate` sobre base vacía, pruebas de modelo.
- [ ] **Fase 5 —** `verify`, validador, commit.

## 6. Criterios de aceptación
- [ ] `migrate` desde base vacía sin errores (salida en bitácora).
- [ ] `makemigrations --check --dry-run` → `No changes detected`.
- [ ] Campos comparados uno a uno contra `CLAUDE.md` (lista en la bitácora).
- [ ] `verify` en verde.

## 7. Checklist de cumplimiento
Nombres exactos de `CLAUDE.md` · ORM portable a PostgreSQL (nada específico de SQLite).

## 8. Riesgos y rollback
- **Pregunta abierta:** ¿nombre de la FK/O2O? Propuesta: `registro`.
- **Rollback:** borrar la rama y `db.sqlite3`.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
