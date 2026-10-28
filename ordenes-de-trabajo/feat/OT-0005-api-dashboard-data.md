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

**Alcance ampliado durante la ejecución:**
- Campos extra en el JSON que la UI de OT-0006 necesita y que salen de la misma fuente:
  `kpis.energia_servida_kwh`, `kpis.potencia_bateria_actual_kw`, `umbrales_soc` (15/25/40 %,
  de la cabecera del seeder: las bandas del gráfico no se teclean en JS), `financiero.anio_reemplazo_baterias`,
  `analitica.anomalias[].variable` y `metricas.*.n`.
- `payback_anios` se llama **`payback_simple_anios`**: es sin descontar (OT-0004 §8) y el
  nombre lo dice.
- `rango.sin_datos` pasó al nivel superior (`sin_datos`), y con base vacía `kpis`/`segmentos`/
  `analitica` son `null`: la UI distingue «sin datos» de «ceros».
- **Métricas de generación sólo en horas con sol** (real o predicha > 0): las noches, 0 contra
  0, inflaban el R² sin decir nada del modelo. Demanda: todas las horas.

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
- [x] **Fase 1 —** Parseo/validación de parámetros y ventana anclada, con pruebas (400s incluidos).
- [x] **Fase 2 —** `services.py`: payload de KPIs, series, segmentos.
- [x] **Fase 3 —** Analítica (métricas + anomalías) y financiero (resumen + flujo + payback).
- [x] **Fase 4 —** Vistas, URLs (`/` y `/api/dashboard-data/`), plantilla mínima de `/`.
- [x] **Fase 5 —** Pruebas de contrato (claves y longitudes), `assertNumQueries`, base vacía.
- [x] **Fase 6 —** `verify`, validador, commit; `curl` real con tamaños en la bitácora.

## 6. Criterios de aceptación
- [x] `dias=1/7/30` devuelven 24/168/720 puntos (medido con `curl` sobre la base sembrada).
- [x] Parámetros inválidos → 400; base vacía → 200 con `sin_datos: true`.
- [x] Nº de consultas constante e independiente del rango (`assertNumQueries`).
- [x] Σ `totales_kwh` de segmentos == `kpis.demanda_kwh` (prueba).
- [x] `verify` en verde.

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
| 2026-10-28 | — | **Implementado:** `monitoreo/services.py` (validación del rango + armado del payload, separado de la vista), `views.py` (`require_GET`, 400 con `{"error"}`), `urls.py` (`/` y `/api/dashboard-data/`), plantilla provisional de `/`. |
| 2026-10-28 | — | **Medido con el cliente de pruebas sobre la base sembrada:** `dias=1/7/30` → 24/168/720 registros (7,9 KB / 24,6 KB / 88,1 KB); sin parámetros → 168; `desde=2026-10-10&hasta=2026-10-11` → 48, de 00:00 a 23:00 −05:00; `dias=abc`, `desde>hasta`, sólo `desde` → 400 con mensaje; POST → 405; `/` → 200. |
| 2026-10-28 | — | **KPIs (30 días):** generación 6 323,66 · demanda 4 855,31 · servida 4 639,81 · vertimiento 1 521,05 · no suministrada 215,5 kWh (la simulación dio 216: el residuo `gen − dem − p_bat` reproduce el despacho) · ahorro 13 919 425 COP · 3,712 tCO₂ · pico 21,28 kWh el 21-10 09:00 (la anomalía PICO_CONSUMO). Participación: residencial 44,6 %, productivo 30,1 %, comunitario 14,2 %, alumbrado 11,1 %. Métricas: generación MAE 1,264 · RMSE 2,891 · R² 0,928 (n = 360); demanda MAE 0,382 · RMSE 0,549 · R² 0,978 (n = 720). Payback simple 7,02 años; diésel nivelado 3 705,19. |
| 2026-10-28 | — | **`verify`: `Ran 97 tests … OK`** (+16 de la API). Consultas: 5 por `dias` (1 o 30) y 4 por fechas. **Control negativo:** sin `select_related("analitica")` → `29 != 5` (dias=1) y `725 != 5` (dias=30); restaurado → OK. |
| 2026-10-28 | — | **Validador, 1.ª pasada: ❌ bloquear.** Reprodujo todas las cifras de arriba y midió 5/4/3/0 consultas (días / fechas / fuera de datos / 400). Bloqueantes: (1) `?dias=²` → **500** (`str.isdigit()` acepta dígitos Unicode que `int()` rechaza) con traceback visible por `DEBUG=1`; (2) `?desde=2026-01-01&hasta=9999-12-31` → **500** (`OverflowError` al pasar a UTC). Menores: `fromisoformat` aceptaba `20261010`/`2026-W41-1`; el JSON sin datos cambiaba de forma; fin del día con `time(23)`; prueba con petición duplicada; faltaban pruebas de `umbrales_soc`, `energia_servida_kwh`, offset y `dias=`. |
| 2026-10-28 | — | **Correcciones:** `PATRON_DIAS` (`[0-9]{1,3}`, ASCII) y `PATRON_FECHA` estrictos; `_momento_local()` comprueba la conversión a UTC → 400 «Fecha fuera del rango admitido»; `time.max`; payload vacío con las 11 claves de `series` y `umbrales_soc` siempre presente; 7 casos hostiles nuevos en la prueba de 400 y 3 pruebas nuevas. **Medido:** `verify` → `Ran 100 tests … OK`; contra la base real `dias=²` → 400 y `hasta=9999-12-31` → 400; **fuzz de 3 000 peticiones aleatorias → {400: 2 705, 200: 295}, cero 500.** HEAD → 405 (`require_GET`) se deja: el dashboard sólo usa GET. |
| 2026-10-28 | — | **Validador, 2.ª pasada (reanudado): ✅ aprobar.** Reprodujo ambos bloqueantes ya en 400 (con `DEBUG=0`) y probó más entradas hostiles (`٧`, 7 de ancho completo, `7\0`, `7\n`, `0000-01-01`, fecha con `\n`): todas 400, ningún 500. Sin regresiones: mismas consultas, mismos puntos, misma forma del JSON con y sin datos, mismas cifras. |
| 2026-10-28 | — | **Ampliado desde OT-0006 (misma causa: una sola fuente):** el JSON añade `parametros` (kWp, kWh de batería, pérdida térmica, error de predicción, umbrales del detector), que la UI cita en sus textos. Prueba `ApiParametrosTests`. |
