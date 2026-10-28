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
  - `financiero/parametros.py` — **única fuente** de los parámetros técnico-económicos.
  - `financiero/calculos.py` — flujo de caja, VPN, TIR (bisección), LCOE, payback.
- `monitoreo/management/commands/seed_amalfi_data.py`: borra lo previo y persiste todo en
  **una transacción** con `bulk_create`. Opciones: `--dias` (30), `--semilla` (42).
- Pruebas de invariantes (§6) y ejecución real del comando.

**Qué NO entra:** API y UI (OT-0005/0006); ingesta CSV o `.joblib` (ADR-0001).

**Alcance ampliado durante la ejecución:** _(vacío)_

## 4. Diseño / enfoque técnico

### 4.1 Ventana temporal
- 720 horas consecutivas que **terminan en la última hora completa** antes de `now()` en
  `America/Bogota`. Timestamps *aware*. Los perfiles horarios usan la hora local.
- `random.Random(semilla)` propio: misma semilla → mismos datos (reproducible).

### 4.2 Clima e irradiancia (Amalfi: andino, húmedo, ~1 550 m s. n. m.)
- **Tipo de día** por cadena de Markov con persistencia: *despejado*, *parcial*, *nublado*.
  Se fuerza **un frente lluvioso de 3 días seguidos** en posición aleatoria, para que la
  batería pase por `ALERTA` y `CRITICO` (si no, el semáforo nunca se pone rojo).
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
| `RESIDENCIAL` (~60 viviendas) | base nocturna, rampa mañana, **pico 18:00–21:00** | ≈ 65 kWh |
| `PRODUCTIVO` (trapiche/beneficiadero) | **pico 09:00–15:00**; sábado 60 %, domingo 15 % | ≈ 55 kWh |
| `COMUNITARIO` (escuela/puesto de salud) | **08:00–16:00**; fin de semana 20 % | ≈ 28 kWh |
| `ALUMBRADO` (luminarias LED) | constante **18:00–06:00**, 0 de día | ≈ 18 kWh |
`demanda_total_kwh` = **suma exacta** de los 4 segmentos. Total ≈ 165 kWh/día entre semana.

### 4.6 Batería (banco de 120 kWh) — despacho hora a hora
- `SoC₀ = 70 %`; operación entre **15 % y 100 %**; eficiencias carga/descarga 0.95/0.95.
- Excedente → carga (`potencia_bateria_kw > 0`) hasta 100 %; lo que sobra es **vertimiento**.
- Déficit → descarga (`< 0`) hasta 15 %; lo que falta es **energía no suministrada**.
- `autonomia_horas = (SoC − 15 %)·120 kWh / demanda media de las últimas 24 h`.
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

### 4.8 Financiero (`financiero/parametros.py` + `calculos.py`)
- Año 0: `flujo_neto = −CAPEX`. Años 1–25:
  - `ingresos_ahorro = E_anual · costo_diesel_evitado · (1+esc)^(t−1) · (1−deg)^(t−1)`
  - `costos_om = OPEX · (1+infl)^(t−1)` **+ reemplazo de baterías en el año 10**
  - `flujo_neto = ingresos − costos`; `flujo_acumulado` = suma corrida.
- **VPN, TIR y LCOE se calculan del flujo sembrado** (no se teclean): TIR por bisección,
  `LCOE = (CAPEX + Σ VP(costos)) / Σ VP(energía)`.
- Parámetros iniciales a calibrar en la Fase 6 (los valores finales y la aritmética van a la bitácora):

  | Parámetro | Propuesta | Clase de evidencia |
  |---|---|---|
  | CAPEX (50 kWp + 120 kWh + red + logística ZNI) | ≈ COP 1 100–1 200 M | afirmado, a calibrar |
  | OPEX anual | ≈ 1,5 % del CAPEX | afirmado |
  | Reemplazo baterías año 10 | ≈ COP 130 M | afirmado |
  | Costo diésel evitado | ≈ COP 3 000 /kWh | afirmado — fuente pendiente (IPSE/CREG) |
  | Escalamiento diésel / inflación OPEX | 3 % / 3 % | afirmado |
  | Degradación FV | 0,5 %/año | afirmado (típico de fabricante) |
  | Factor de emisión diésel | 0,80 kgCO₂/kWh (2,68 kg/L × 0,30 L/kWh) | derivado de afirmados |
  | Tasa de descuento | **10 %** | **pregunta abierta §8** |
  | Energía anual servida | ≈ 56 MWh | se contrasta con el mes simulado ×365/30 (±15 %) |
- **Meta:** TIR ∈ [14,0 %, 15,0 %], VPN > 0, LCOE < costo diésel evitado. Se calibra **el
  CAPEX** (no la TIR) hasta cumplirla, y se escribe la aritmética.

## 5. Plan por fases
- [ ] **Fase 1 —** `financiero/parametros.py` con constantes nombradas y unidades.
- [ ] **Fase 2 —** `simulacion.py`: clima + irradiancia + temperaturas + generación, con pruebas.
- [ ] **Fase 3 —** `simulacion.py`: demanda por segmento, con pruebas de perfiles.
- [ ] **Fase 4 —** `analitica/services.py`: inyección, predicción, detector, métricas, con pruebas.
- [ ] **Fase 5 —** `simulacion.py`: despacho de batería, SoC, autonomía y estado, con pruebas.
- [ ] **Fase 6 —** `financiero/calculos.py`: flujo, VPN, TIR, LCOE, payback; calibración documentada.
- [ ] **Fase 7 —** Comando `seed_amalfi_data` (transacción + `bulk_create`), prueba del comando
      (idempotente y reproducible) y ejecución real; resumen medido en la bitácora.
- [ ] **Fase 8 —** `verify`, validador, commit.

## 6. Criterios de aceptación (invariantes probadas)
- [ ] 720 registros, horas consecutivas sin huecos; re-ejecutar deja 720 (idempotente); misma
      semilla → mismos datos.
- [ ] Irradiancia 0 fuera de 06–18; picos de días despejados ∈ [750, 1 000] W/m².
- [ ] T_amb ∈ [17, 30] °C; T_panel ≥ T_amb y ≤ 49 °C.
- [ ] Generación 0 de noche y ≤ 50 kWh/h.
- [ ] `demanda_total_kwh == Σ segmentos` en cada hora; picos de cada segmento en su ventana.
- [ ] SoC ∈ [15, 100]; cada ΔSoC cuadra con `potencia_bateria_kw` y las eficiencias;
      `estado_sistema` cuadra con los umbrales; aparecen los **tres** estados en el mes.
- [ ] Error de predicción ∈ [3 %, 8 %] en horas normales con valor > 0.
- [ ] 6–8 anomalías; detectadas == inyectadas.
- [ ] 26 filas de flujo; acumulado = suma corrida; pico de costos en el año 10;
      TIR recalculada del flujo == `tir_porcentaje` (±0,01) y ∈ [14, 15]; VPN > 0;
      LCOE < costo diésel evitado.
- [ ] `verify` en verde; comando ejecutado con su resumen en la bitácora.

## 7. Checklist de cumplimiento
Sin magic numbers: toda constante física/económica con nombre y unidad · lógica pura sin ORM ·
ninguna cifra financiera tecleada que pueda calcularse del flujo.

## 8. Riesgos y rollback
- **Pregunta abierta — tasa de descuento:** propongo 10 %. ¿La autora del trabajo usa otra
  (p. ej., la tasa social de descuento del DNP)?
- **Pregunta abierta — parámetros económicos:** CAPEX, costo del diésel y factor de emisión son
  *afirmados*. ¿Hay cifras del trabajo de grado que deban usarse en su lugar?
- **Riesgo:** con ciertos climas el SoC nunca baja de 25 % → el frente lluvioso forzado lo
  garantiza y la prueba lo exige.
- **Rollback:** borrar la rama; `seed_amalfi_data` es idempotente.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | **Pre-calibración (medido, script de borrador, no el código final):** con E = 56 500 kWh, diésel 3 000 COP/kWh, esc. 3 %, deg. 0,5 %, OPEX 1,5 % CAPEX, reemplazo 130 M en año 10, r = 10 %: CAPEX 1 100 M → TIR 15,24 %, VPN 531 M, LCOE 2 712; **CAPEX 1 150 M → TIR 14,49 %, VPN 472 M, LCOE 2 830, payback año 8**; CAPEX 1 200 M → TIR 13,80 %. Ojo: el margen LCOE vs. diésel es estrecho (≈ 6 %); si el diésel real de la zona es más caro, el margen crece. |
