---
id: OT-0004
tipo: feat
titulo: "Generador de datos sintéticos físicamente coherentes (seed_amalfi_data)"
rama: "feat/ot-0004-seed-amalfi"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: [OT-0003]
docs_ref: [CLAUDE.md §2 §4, docs/adr/ADR-0001-mvp-con-datos-sinteticos.md]
creado: 2026-10-28
---

# OT-0004 — Generador de datos sintéticos físicamente coherentes (`seed_amalfi_data`)

## 1. Contexto y problema
Según ADR-0001, todo el MVP se alimenta de un generador. Si los datos no son físicamente
coherentes (generación de noche, SoC que sube sin excedente, demanda que no suma sus
segmentos, TIR que no sale del flujo), el dashboard se ve bien pero **no defiende el trabajo
de grado**.

## 2. Objetivo
`python manage.py seed_amalfi_data` deja en la base **720 registros horarios** de los últimos
30 días, sus 4 segmentos por hora, sus predicciones con **6–8 anomalías detectables**, un
`ResumenFinanciero` y **26 filas** de `FlujoCajaAnual` (años 0–25), y una batería de pruebas
de invariantes físicas y financieras lo comprueba.

## 3. Alcance
**Qué SÍ entra:**
- Lógica pura (sin ORM, testeable) separada del comando:
  - `monitoreo/simulacion.py` — clima, irradiancia, temperaturas, generación, demanda por segmento, batería.
  - `analitica/services.py` — predicción mock, inyección y detección de anomalías, métricas MAE/RMSE/R².
  - Cabecera de `seed_amalfi_data.py` — **única fuente** de los parámetros técnico-económicos (decisión del lead, §4.8).
  - `financiero/calculos.py` — flujo de caja, VPN, TIR (bisección), LCOE, payback.
- `monitoreo/management/commands/seed_amalfi_data.py`: borra lo previo y persiste todo en
  **una transacción** con `bulk_create`. Opciones: `--dias` (30), `--semilla` (42).
- Pruebas de invariantes (§6) y ejecución real del comando.

**Qué NO entra:** API y UI (OT-0005/0006); ingesta CSV o `.joblib` (ADR-0001).

**Alcance ampliado durante la ejecución:**
- **Una hora por anomalía** (no 1–3 h): así «6–8 anomalías» son 6–8 filas en la tabla de la
  pestaña de Analítica, sin ambigüedad entre eventos y horas.
- El detector también clasifica desvíos en sentido opuesto (`GENERACION_ATIPICA`,
  `CAIDA_DEMANDA`): no se inyectan, pero un detector que sólo ve lo que se le inyectó no
  detecta nada.
- `--dias` mínimo 14 (`DIAS_MINIMOS`): con menos no caben 6–8 anomalías en días distintos
  más el frente; el comando falla con mensaje en vez de generar datos a medias.
- Factores de anomalía ajustados al diseñar el umbral del detector: pico productivo ×2,0–2,8
  (no ×1,8–2,5) y nocturno ×3,5–4,5 (no ×2), porque con los valores originales el desvío
  mínimo (tras el error de predicción de hasta 8 %) quedaba por debajo de 30 % / 2 kWh.
- Picos de irradiancia acotados a 1 000 W/m² (`min`) para respetar el rango pedido.

## 4. Diseño / enfoque técnico

### 4.1 Ventana temporal
- 720 horas consecutivas que **terminan en la última hora completa** antes de `now()` en
  `America/Bogota`. Timestamps *aware*. Los perfiles horarios usan la hora local.
- `random.Random(semilla)` propio: misma semilla → mismos datos (reproducible).

### 4.2 Clima e irradiancia (Amalfi: andino, húmedo, ~1 550 m s. n. m.)
- **Tipo de día** por cadena de Markov con persistencia: *despejado*, *parcial*, *nublado*.
  Se fuerza **un frente lluvioso de 3 días seguidos** en posición aleatoria (temporada de
  lluvias de octubre). ~~Para que la batería pase por `ALERTA` y `CRITICO`~~ — **refutado por
  medición** (§9): sin el frente, las 30 semillas de prueba muestran igual los tres estados.
- Campana: `G(h) = G_max · sin(π·(h+0.5−6)/12)` para 06:00–18:00, 0 fuera.
  `G_max` del día ∈ [850, 1000] W/m² × factor del tipo de día; ruido horario de nubosidad,
  más fuerte en la tarde (convección andina). Picos de días despejados: 750–1 000 W/m².

### 4.3 Temperaturas
- Ambiente: curva diaria con mínimo ≈ 18 °C hacia las 05:00 y máximo ≈ 29 °C hacia las 14:00;
  amplitud reducida en días nublados.
- Panel: `T_p = T_a + k·G`, `k = 0.019 °C·m²/W` → con 1 000 W/m² y 29 °C da ≈ 48 °C.

### 4.4 Generación FV (planta de 50 kWp)
`E_h [kWh] = P_stc · (G/1000) · (1 + γ·(T_p − 25)) · η_bos`, con `P_stc = 50 kWp`,
`γ = −0.0040 /°C`, `η_bos = 0.86` (inversor, cableado, suciedad). Máximo ≈ 39 kWh/h.

### 4.5 Demanda por segmento (kWh/h; perfiles con ruido ±10 %)
| Segmento | Perfil | Día típico (entre semana) |
|---|---|---|
| `RESIDENCIAL` (~60 viviendas) | base nocturna, rampa mañana, **pico 18:00–21:00** | ≈ 72 kWh |
| `PRODUCTIVO` (trapiche/beneficiadero) | **pico 09:00–15:00**; sábado 60 %, domingo 15 % | ≈ 58 kWh |
| `COMUNITARIO` (escuela/puesto de salud) | **08:00–16:00**; fin de semana 20 % | ≈ 28 kWh |
| `ALUMBRADO` (luminarias LED) | constante **18:00–06:00**, 0 de día | ≈ 18 kWh |
`demanda_total_kwh` = **suma exacta** de los 4 segmentos. Total ≈ 177 kWh/día entre semana
(≈ 131 sábado, ≈ 105 domingo; medido en el mes: 161,8 kWh/día de media).

### 4.6 Batería (banco de 120 kWh) — despacho hora a hora
- `SoC₀ = 70 %`; operación entre **15 % y 100 %**; eficiencias carga/descarga 0.95/0.95.
- Excedente → carga (`potencia_bateria_kw > 0`) hasta 100 %; lo que sobra es **vertimiento**.
- Déficit → descarga (`< 0`) hasta 15 %; lo que falta es **energía no suministrada**.
- `autonomia_horas = (SoC − 15 %)·120 kWh·η_descarga / demanda media de las últimas 24 h`
  (con η_descarga: es la energía que la batería **entrega**, no la que almacena).
- `estado_sistema`: `OPTIMO` si SoC ≥ 40 · `ALERTA` si 25 ≤ SoC < 40 · `CRITICO` si < 25.
- Vertimiento y energía no suministrada **no tienen campo** en `CLAUDE.md`: se derivan en la
  API (OT-0005) como el residuo del balance, sin tocar el esquema.

### 4.7 Predicciones mock y anomalías (`analitica`)
- `predicha = esperado · (1 ± ε)`, `|ε| ~ U(0.03, 0.08)`, signo aleatorio; «esperado» es el
  valor **sin anomalía**. De noche, generación predicha = 0.
- **Inyección de 6–8 anomalías** en días distintos y fuera del frente lluvioso, **antes** del
  despacho de la batería (el SoC las refleja):

  | `tipo_anomalia` | Qué se altera | Ventana |
  |---|---|---|
  | `FALLA_INVERSOR` | generación → 0–10 % del esperado, 1–3 h | 10:00–14:00 |
  | `SOMBREADO_PARCIAL` | generación −40 a −60 %, 1–2 h | 10:00–14:00 |
  | `PICO_CONSUMO` | demanda productiva ×1.8–2.5 (arranque de motores) | 09:00–15:00 |
  | `CONSUMO_NOCTURNO_ATIPICO` | demanda ×2+ (posible conexión irregular) | 01:00–04:00 |
  Al menos una de cada una de las tres primeras.
- `descripcion_anomalia` con cifras: *«Generación real 3,1 kWh vs. 34,8 kWh esperados (−91 %)
  a las 12:00. Posible disparo del inversor.»*
- **Detector**: regla `|real − predicho| / predicho > 30 %` y `|real − predicho| > 2 kWh`.
  Con ruido ≤ 8 % sólo puede disparar en lo inyectado → la prueba exige
  **detectadas == inyectadas** (control negativo: ninguna hora normal marcada).
- `es_anomalia` lo fija el detector, no la inyección: así la tabla muestra lo que un sistema
  real vería.

### 4.8 Financiero (constantes en `seed_amalfi_data.py` + `financiero/calculos.py`)
> **Decisión del lead (2026-10-28):** todas las variables financieras y ambientales se
> declaran como **constantes documentadas en la parte superior de `seed_amalfi_data.py`**
> (no en `financiero/parametros.py`), para que la autora las ajuste en un solo lugar. Esa
> cabecera es la **única fuente**: la API (OT-0005) las importa de ahí. Lo mismo para los
> parámetros físicos de la planta (kWp, kWh de batería, umbrales de SoC).
- Año 0: `flujo_neto = −CAPEX`. Años 1–25:
  - `ingresos_ahorro = E_anual · costo_diesel_evitado · (1+esc)^(t−1) · (1−deg)^(t−1)`
  - `costos_om = OPEX · (1+infl)^(t−1)` **+ reemplazo de baterías en el año 10**
  - `flujo_neto = ingresos − costos`; `flujo_acumulado` = suma corrida.
- **VPN, TIR y LCOE se calculan del flujo sembrado** (no se teclean): TIR por bisección,
  `LCOE = (CAPEX + Σ VP(costos)) / Σ VP(energía)`.
- Parámetros iniciales a calibrar en la Fase 6 (los valores finales y la aritmética van a la bitácora):

  | Constante | Valor | Clase de evidencia |
  |---|---|---|
  | `CAPEX_COP` (50 kWp + 120 kWh + red + logística ZNI) | ≈ COP 1 150 M | afirmado, calibrado a la TIR meta |
  | `OPEX_FRACCION_CAPEX` | 1,5 % del CAPEX | afirmado |
  | `REEMPLAZO_BATERIAS_COP` / `ANIO_REEMPLAZO_BATERIAS` | COP 130 M / año 10 | afirmado |
  | `COSTO_DIESEL_EVITADO_COP_KWH` | 3 000 COP/kWh (año 1) | afirmado — **aprobado por el lead** |
  | `ESCALAMIENTO_DIESEL` / `INFLACION_OPEX` | 3 % / 3 % | afirmado |
  | `DEGRADACION_FV_ANUAL` | 0,5 %/año | afirmado (típico de fabricante) |
  | `FACTOR_EMISION_KGCO2_KWH` | 0,80 (2,68 kg/L × 0,30 L/kWh) | derivado de afirmados — **aprobado por el lead** |
  | `TASA_DESCUENTO` | **12 % E.A.** (referencia TSD del DNP) | **decisión del lead** |
  | `ENERGIA_ANUAL_SERVIDA_KWH` | ≈ 56 500 kWh | se contrasta con el mes simulado ×365/30 (±15 %) |
- **Comparación LCOE vs. diésel, con la misma vara:** el LCOE solar se compara con el **costo
  nivelado del diésel** (3 000 COP/kWh escalando 3 %/año, descontado al mismo 12 % y con la
  misma energía), no con el precio del año 1. Comparar un costo nivelado con uno de año 1
  mezcla magnitudes distintas. Se calcula en `calculos.py` y se expone en la API.
- **Ojo (validador):** con la misma tasa, energía y horizonte, «LCOE < diésel nivelado» es
  matemáticamente equivalente a «VPN > 0» (VPN = VP(energía) × (LCOD − LCOE)); no es una
  evidencia independiente, es la misma dicha en COP/kWh.
- **Meta:** TIR ∈ [14,0 %, 15,0 %], VPN > 0 al 12 %, LCOE < costo nivelado del diésel. Se
  calibra **el CAPEX** (no la TIR) y se escribe la aritmética.

## 5. Plan por fases
- [x] **Fase 0 —** Decisiones del lead (2026-10-28): tasa 12 % E.A.; diésel 3 000 COP/kWh;
      factor 0,8 kgCO₂/kWh; constantes en la cabecera del seeder.
- [x] **Fase 1 —** Cabecera de constantes de `seed_amalfi_data.py` (nombre, valor, unidad y fuente en cada una).
- [x] **Fase 2 —** `simulacion.py`: clima + irradiancia + temperaturas + generación, con pruebas.
- [x] **Fase 3 —** `simulacion.py`: demanda por segmento, con pruebas de perfiles.
- [x] **Fase 4 —** `analitica/services.py`: inyección, predicción, detector, métricas, con pruebas.
- [x] **Fase 5 —** `simulacion.py`: despacho de batería, SoC, autonomía y estado, con pruebas.
- [x] **Fase 6 —** `financiero/calculos.py`: flujo, VPN, TIR, LCOE, payback; calibración documentada.
- [x] **Fase 7 —** Comando `seed_amalfi_data` (transacción + `bulk_create`), prueba del comando
      (idempotente y reproducible) y ejecución real; resumen medido en la bitácora.
- [x] **Fase 8 —** `verify`, validador, commit.

## 6. Criterios de aceptación (invariantes probadas)
- [x] 720 registros, horas consecutivas sin huecos; re-ejecutar deja 720 (idempotente); misma
      semilla → mismos datos.
- [x] Irradiancia 0 fuera de 06–18; picos de días despejados ∈ [750, 1 000] W/m².
- [x] T_amb ∈ [17, 30] °C; T_panel ≥ T_amb y ≤ 49 °C.
- [x] Generación 0 de noche y ≤ 50 kWh/h.
- [x] `demanda_total_kwh == Σ segmentos` en cada hora; picos de cada segmento en su ventana.
- [x] SoC ∈ [15, 100]; cada ΔSoC cuadra con `potencia_bateria_kw` y las eficiencias;
      `estado_sistema` cuadra con los umbrales; aparecen los **tres** estados en el mes.
- [x] Error de predicción ∈ [3 %, 8 %] en horas normales con valor > 0.
- [x] 6–8 anomalías; detectadas == inyectadas.
- [x] 26 filas de flujo; acumulado = suma corrida; pico de costos en el año 10;
      TIR recalculada del flujo == `tir_porcentaje` (±0,01) y ∈ [14, 15]; VPN > 0 al 12 %;
      LCOE < costo nivelado del diésel.
- [x] `verify` en verde; comando ejecutado con su resumen en la bitácora.

## 7. Checklist de cumplimiento
Sin magic numbers: toda constante física/económica con nombre y unidad · lógica pura sin ORM ·
ninguna cifra financiera tecleada que pueda calcularse del flujo.

## 8. Riesgos y rollback
- **Resuelto (2026-10-28):** tasa 12 % E.A.; diésel 3 000 COP/kWh y 0,8 kgCO₂/kWh aprobados.
  Siguen siendo *afirmados*: si la autora actualiza un supuesto, se cambia la constante y se
  vuelve a correr el seeder; las pruebas de §6 dicen si la TIR sale de [14, 15].
- **Riesgo:** con ciertos climas el SoC nunca baja de 25 % → el frente lluvioso forzado lo
  garantiza y la prueba lo exige.
- **Pregunta abierta — tasa real vs. nominal (validador):** la TSD del DNP es una tasa **real**,
  pero el diésel y el O&M escalan un 3 % anual que parece **nominal**. Para ser consistentes:
  (a) leer los 3 % como escalamientos **reales** (por encima de la inflación — exigente para el
  O&M), o (b) bajarlos a ~0–1 % real, lo que reduce la TIR y obligaría a recalibrar el CAPEX.
  Decisión de la autora/lead; hoy queda (a) documentado.
- **Payback:** es **simple** (sin descontar); la UI debe rotularlo así.
- **Rollback:** borrar la rama; `seed_amalfi_data` es idempotente.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | **Pre-calibración (medido, script de borrador, no el código final):** con E = 56 500 kWh, diésel 3 000 COP/kWh, esc. 3 %, deg. 0,5 %, OPEX 1,5 % CAPEX, reemplazo 130 M en año 10, r = 10 %: CAPEX 1 100 M → TIR 15,24 %, VPN 531 M, LCOE 2 712; **CAPEX 1 150 M → TIR 14,49 %, VPN 472 M, LCOE 2 830, payback año 8**; CAPEX 1 200 M → TIR 13,80 %. Ojo: el margen LCOE vs. diésel es estrecho (≈ 6 %); si el diésel real de la zona es más caro, el margen crece. |
| 2026-10-28 | — | **Recalculado con r = 12 % (decisión del lead), mismo script:** la TIR no depende de r (CAPEX 1 150 M → 14,49 %); VPN 228 M; LCOE 2 830 → **3 173 COP/kWh**, que ya **supera** los 3 000 del año 1. Comparado con el **costo nivelado del diésel** al 12 % (3 000 escalando 3 %, misma energía) = **3 705 COP/kWh** → el solar es ≈ 14 % más barato. Se adopta esa comparación (§4.8). |
| 2026-10-28 | — | **Implementado:** `financiero/calculos.py`, `analitica/services.py`, `monitoreo/simulacion.py`, comando con cabecera de supuestos (`PLANTA`, `FINANZAS`). Lógica pura separada del ORM; el comando sólo orquesta y persiste en una transacción con `bulk_create`. |
| 2026-10-28 | — | **Ejecución real (semilla 42, medido en la base):** 720 h (2026-09-28 15:00 → 2026-10-28 14:00). G máx 986 W/m²; T_amb 17,8–29,3 °C; T_panel máx 46,7 °C; gen. máx 39,0 kWh/h; SoC 15,0–100,0 %; potencia +28,3 / −11,9 kW; autonomía máx 22,2 h. Estados: OPTIMO 546 · ALERTA 94 · CRITICO 80. Generación 6 324 kWh (210,8/día), demanda 4 855 kWh (161,8/día), vertimiento 1 521, no suministrada 216 (4,4 % de la demanda). Segmentos: residencial 2 165, productivo 1 462, comunitario 689, alumbrado 540 kWh. 8 anomalías inyectadas = 8 detectadas (2 falla de inversor, 4 sombreado, 1 pico, 1 nocturna). Tiempo: 0,8 s. |
| 2026-10-28 | — | **Financiero guardado:** CAPEX 1 150 000 000 · OPEX 17 250 000 · VPN 227 919 781 · TIR 14,49 % · LCOE 3 173,35 vs. diésel nivelado 3 705 COP/kWh · ahorro año 1 169 500 000 · 45,2 tCO₂/año. Año 10: costos 152 507 337 (reemplazo). Acumulado: año 7 = −3 468 041, año 8 = +176 592 564 → payback 7,0 años (interpolado). |
| 2026-10-28 | — | **Contraste energía anual:** servida en el mes = 4 855 − 216 = 4 639 kWh × 365/30 = 56 440 kWh vs. constante 56 500 → desvío 0,1 % (la prueba admite 15 %). |
| 2026-10-28 | — | **`verify`: `Ran 81 tests … OK`** (+60: 29 de simulación, 13 de analítica, 12 de cálculos, 9 del comando; incluye robustez en 30 semillas). Un primer fallo fue de la prueba (el primer día de la ventana empieza a las 15:00 y no tiene mediodía), no del generador: se limitó a fechas con mediodía. |
| 2026-10-28 | — | **Controles negativos (mutantes, restaurados después):** M2 descarga sin η en el SoC → `BateriaTests` FAIL; M3 error de predicción hasta 35 % → robustez FAIL en 30/30 semillas (falsos positivos); M4 sombreado de sólo −10 % → FAIL 30/30 (anomalía no detectada); capex ×2 → TIR < 14 % (prueba incluida). |
| 2026-10-28 | — | **Mecanismo atribuido refutado (M1):** sin frente lluvioso, las 30 semillas siguen mostrando los tres estados (p. ej., semilla 42: CRITICO 61 h; semilla 2: 220 h). Lo que produce ALERTA/CRITICO es la descarga nocturna (~70 kWh) más las tardes nubladas, no el frente. Se mantiene el frente (temporada de lluvias) y se corrigió su justificación en el código y en §4.2. |
| 2026-10-28 | — | **Punto para el lead:** la irradiación media simulada es **5,24 kWh/m²/día** (157 200 Wh/m² / 30). Para Amalfi las referencias habituales rondan 4–5 kWh/m²/día (*afirmado*, fuente pendiente: atlas IDEAM). Bajarla aumentaría la energía no suministrada y obligaría a recalibrar `ENERGIA_ANUAL_SERVIDA_KWH`. |
| 2026-10-28 | — | **Validador (subagente, sólo lectura): ⚠️ aprobar con menores, nada bloquea.** Reprodujo **todas** las cifras de esta bitácora (estados, energías, segmentos, anomalías, VPN/TIR/LCOE, acumulados) y comprobó VPN = VP(E)·(LCOD − LCOE) = 428 543 × 531,8 ≈ 227,9 M. Robustez: 1 680 combinaciones a 30 días sin fallos. Hallazgos atendidos: (1) con `--dias 14`, 52/1 680 escenarios lanzaban `ValueError` sin capturar → los extra sin día compatible se degradan a nocturnos y el comando convierte el error en `CommandError`; (2) la prueba de energía anual regeneraba desde el `timestamp` en UTC (otro escenario, desplazado 5 h; pasaba sin probar nada) → `localtime` + aserción de que es el mismo escenario; (3) prueba de ventana frágil ante un cambio de hora → se miden los inicios antes y después de sembrar; (4) prueba de TIR tautológica en `test_calculos` → eliminada (la de la base sí aporta); (5) metodología → payback rotulado como simple, degradación conservadora documentada, real/nominal elevado al lead (§8), equivalencia LCOE/VPN anotada (§4.8); (6) §4.5 desactualizado → corregido; (7) calidad: generación calculada dos veces, estados literales, `range(6, 9)`, `TAMANO_LOTE` sin comentario, orden de tipos → corregidos. |
| 2026-10-28 | — | **Bug propio cazado por la prueba nueva:** el primer fallback usaba `tipo not in TIPOS_OBLIGATORIOS`, pero un extra puede ser del mismo tipo que un obligatorio (mismo texto) → nunca se degradaba. Se decide por **posición** en la lista. |
| 2026-10-28 | — | **Tras las correcciones (medido):** 3 360 combinaciones (14 y 30 días × inicios 00/01/15/23 h × 7 fechas × semillas 1–60): **0 `ValueError`, 0 desajustes** detectadas≠inyectadas. Semilla 42 re-sembrada: cifras idénticas a las de arriba (el reordenamiento conserva el consumo del RNG). `verify`: `Ran 81 tests … OK`. |
| 2026-10-28 | — | **Decisiones del lead sobre los 3 puntos abiertos:** (1) el 3 % de escalamiento del diésel y del O&M se lee como **real** (por encima de la inflación; logística en ZNI) → no se toca la calibración ni la semilla 42; (2) la irradiación de 5,24 kWh/m²/día se mantiene; si la autora la ajusta al dato del IDEAM, lo hará desde las constantes del seeder; (3) la equivalencia LCOE < diésel nivelado ⇔ VPN > 0 se anota para el documento escrito; el dashboard mantiene ambos indicadores. Visto bueno y merge a `main`. |
