---
id: OT-0005
tipo: feat
titulo: "Vista del dashboard y endpoint /api/dashboard-data/"
rama: "feat/ot-0005-api-dashboard"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: [OT-0004]
docs_ref: [CLAUDE.md, ordenes-de-trabajo/feat/OT-0004-generador-datos-sinteticos.md]
creado: 2026-10-28
---

# OT-0005 — Vista del dashboard y endpoint `/api/dashboard-data/`

## 1. Contexto y problema
El frontend (OT-0006) necesita **un solo JSON** por rango de fechas con todo lo que pintan las
6 pestañas, sin recargar la página.

## 2. Objetivo
`GET /api/dashboard-data/?dias=1|7|30` (o `?desde=AAAA-MM-DD&hasta=AAAA-MM-DD`) responde 200
con el contrato de §4, en un número **acotado** de consultas (medido con
`assertNumQueries`), y `GET /` sirve la plantilla base del dashboard.

## 3. Alcance
**Qué SÍ entra:** `monitoreo/views.py` (vista HTML + vista JSON), `monitoreo/services.py`
(armado del payload, separado de la vista), `urls.py`, validación de parámetros, pruebas.

**Qué NO entra:** el HTML/JS real de las pestañas (OT-0006); autenticación (MVP local).

**Alcance ampliado durante la ejecución:** _(vacío)_

## 4. Diseño / enfoque técnico

### 4.1 Ventana — anclada al último registro, no a `now()`
`dias=N` = las N·24 horas que **terminan en el último `timestamp` de la base**. Si se anclara
a `now()`, una base sembrada hace dos días devolvería «últimas 24 h» vacías. El JSON devuelve
`desde`/`hasta` reales para que la UI los muestre.

### 4.2 Parámetros
- `dias ∈ {1, 7, 30}` (default 7). `desde`/`hasta` (ISO, inclusivos) tienen prioridad sobre `dias`.
- Inválidos (`dias=abc`, `desde > hasta`, fecha mal formada) → **400** con `{"error": "…"}`.
- Base vacía → 200 con series vacías y `"sin_datos": true` (la UI muestra «ejecuta seed_amalfi_data»).

### 4.3 Contrato JSON
```json
{
  "rango":   {"desde": "...", "hasta": "...", "dias": 7, "n_registros": 168, "sin_datos": false},
  "kpis":    {"generacion_kwh": 0, "demanda_kwh": 0, "soc_actual": 0, "autonomia_horas": 0,
              "estado_actual": "OPTIMO", "ahorro_cop": 0, "co2_evitado_t": 0,
              "demanda_pico_kwh": 0, "demanda_pico_ts": "...",
              "vertimiento_kwh": 0, "energia_no_suministrada_kwh": 0},
  "estados": {"OPTIMO": 0, "ALERTA": 0, "CRITICO": 0},
  "series":  {"timestamps": [], "generacion": [], "demanda": [], "irradiancia": [],
              "temp_ambiente": [], "temp_panel": [], "soc": [], "potencia_bateria": [],
              "autonomia": [], "generacion_predicha": [], "demanda_predicha": []},
  "segmentos": {"series": {"RESIDENCIAL": [], "PRODUCTIVO": [], "COMUNITARIO": [], "ALUMBRADO": []},
                "totales_kwh": {}, "participacion_pct": {}},
  "analitica": {"metricas": {"generacion": {"mae": 0, "rmse": 0, "r2": 0},
                             "demanda":    {"mae": 0, "rmse": 0, "r2": 0}},
                "anomalias": [{"timestamp": "...", "tipo": "...", "descripcion": "...",
                               "real_kwh": 0, "predicho_kwh": 0, "desviacion_pct": 0}]},
  "financiero": {"resumen": {"capex_cop": 0, "...": 0}, "payback_anios": 0,
                 "tasa_descuento_pct": 12, "costo_nivelado_diesel_cop_kwh": 0,
                 "flujo": [{"anio": 0, "ingresos_ahorro_cop": 0, "costos_om_cop": 0,
                            "flujo_neto_cop": 0, "flujo_acumulado_cop": 0}]}
}
```
- **Granularidad:** horaria siempre (≤ 720 puntos; Chart.js los maneja). Una sola ruta de
  código, sin agregación condicional.
- **KPIs derivados** (se documenta la fórmula en el código):
  `ahorro_cop` y `co2_evitado_t` = energía servida en el rango × constantes importadas de
  la cabecera de `seed_amalfi_data.py` (única fuente por decisión del lead, OT-0004 §4.8);
  `vertimiento` / `energia_no_suministrada` = residuo del balance horario (OT-0004 §4.6);
  `payback_anios` = primer año con acumulado ≥ 0, interpolado;
  `costo_nivelado_diesel_cop_kwh` = referencia contra la que se compara el LCOE (OT-0004 §4.8).
- **Métricas** MAE/RMSE/R² **sobre el rango pedido**, con `analitica/services.py` (OT-0004).
- **Orden explícito:** `ConsumoPorSegmento` y `PrediccionYAnomalia` no tienen `ordering` por
  defecto (OT-0003); cada consulta pide `order_by("registro__timestamp")` cuando lo necesita.
- **Consultas:** registros + `select_related("analitica")`; segmentos en **una** consulta
  `values()` sobre el rango; financiero en dos. Sin N+1. Se mide con `assertNumQueries`.
- Floats redondeados (2 decimales) para un JSON limpio; dinero como enteros.

## 5. Plan por fases
- [ ] **Fase 1 —** Parseo/validación de parámetros y ventana anclada, con pruebas (400s incluidos).
- [ ] **Fase 2 —** `services.py`: payload de KPIs, series, segmentos.
- [ ] **Fase 3 —** Analítica (métricas + anomalías) y financiero (resumen + flujo + payback).
- [ ] **Fase 4 —** Vistas, URLs (`/` y `/api/dashboard-data/`), plantilla mínima de `/`.
- [ ] **Fase 5 —** Pruebas de contrato (claves y longitudes), `assertNumQueries`, base vacía.
- [ ] **Fase 6 —** `verify`, validador, commit; `curl` real con tamaños en la bitácora.

## 6. Criterios de aceptación
- [ ] `dias=1/7/30` devuelven 24/168/720 puntos (medido con `curl` sobre la base sembrada).
- [ ] Parámetros inválidos → 400; base vacía → 200 con `sin_datos: true`.
- [ ] Nº de consultas constante e independiente del rango (`assertNumQueries`).
- [ ] Σ `totales_kwh` de segmentos == `kpis.demanda_kwh` (prueba).
- [ ] `verify` en verde.

## 7. Checklist de cumplimiento
Inputs validados · sin SQL crudo · solo `GET` (`require_GET`) · una fuente de verdad para los
parámetros económicos.

## 8. Riesgos y rollback
- **Riesgo:** zona horaria — `desde`/`hasta` se interpretan en `America/Bogota`; prueba con
  fechas de borde.
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
