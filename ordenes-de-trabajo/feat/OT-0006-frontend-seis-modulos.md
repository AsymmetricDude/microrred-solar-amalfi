---
id: OT-0006
tipo: feat
titulo: "Frontend del dashboard: 6 módulos con Tailwind, Alpine.js y Chart.js"
rama: "feat/ot-0006-frontend"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: [OT-0005]
docs_ref: [CLAUDE.md §3, ordenes-de-trabajo/feat/OT-0005-api-dashboard-data.md]
creado: 2026-10-28
---

# OT-0006 — Frontend del dashboard: 6 módulos

## 1. Contexto y problema
El trabajo de grado se presenta a través del dashboard. Debe verse como un SaaS energético
moderno y navegar entre 6 pestañas sin recargar.

## 2. Objetivo
`GET /` muestra el dashboard con sidebar fijo, selector global (24 h / 7 d / 30 d) y las 6
pestañas con todos sus gráficos poblados desde `/api/dashboard-data/`, sin errores en la
consola del navegador y usable a 1 280 px y a 390 px de ancho.

## 3. Alcance
**Qué SÍ entra:**
- `templates/monitoreo/base.html` (CDN, fuente Inter, paleta) y `dashboard.html` (6 pestañas).
- `static/monitoreo/dashboard.js`: store de Alpine, `fetch` a la API, fábrica de gráficos.
- Los 6 módulos, cada uno con lo pedido por el lead:

  | # | Pestaña | Contenido |
  |---|---|---|
  | 1 | Resumen General | KPIs con ícono (generación, consumo, SoC, ahorro, CO₂) · semáforo de estado · balance Gen vs. Demanda (barras/líneas) + SoC en eje derecho |
  | 2 | Monitoreo FV | Doble eje: generación (kWh) vs. irradiancia (W/m²) · T panel vs. T ambiente |
  | 3 | Demanda | Curva de carga **apilada** por segmento · tarjeta de demanda pico · dona de participación |
  | 4 | Almacenamiento | SoC % con **bandas** (verde ≥ 40, ámbar 25–40, rojo < 25) · potencia carga/descarga (kW, ±) · KPI autonomía |
  | 5 | Analítica e IA | Real vs. predicción (generación y demanda) con anomalías marcadas · MAE/RMSE/R² · tabla de anomalías (fecha, hora, tipo, diagnóstico) |
  | 6 | Financiero | Tarjetas CAPEX, OPEX, VPN (al 12 %), TIR, LCOE vs. costo nivelado del diésel · barras (flujo neto) + línea (acumulado) a 25 años con **marca del payback** |
- Rótulo visible «Datos sintéticos — caso de estudio» (ADR-0001).
- Estados de carga, error y base vacía.

**Qué NO entra:** cambios al contrato de la API (si algo falta, se amplía OT-0005 por regla de
raíz y se anota aquí); modo oscuro; recálculo financiero interactivo (`CLAUDE.md` §2).

**Alcance ampliado durante la ejecución:**
- **Playwright + Chromium adelantados desde OT-0007** (dependencia de desarrollo): hacían falta
  para *ver* lo renderizado (la skill `dataviz` exige mirar el resultado) y para correr el
  validador de paleta, porque en este WSL no hay Node. A Chromium le faltaban 4 librerías del
  sistema (`libnspr4`, `libnss3`, `libnssutil3`, `libasound`) y no hay `sudo`: se bajaron los
  `.deb` oficiales de Ubuntu con `apt-get download` y se extrajeron en
  `~/.cache/sun-ia-chromium-deps/` (fuera del repo; se usa con `LD_LIBRARY_PATH`). OT-0007 debe
  documentarlo en el README.
- **Capturas** de las 6 pestañas (30 días, 1 440 px) y una móvil en `docs/capturas/` (1,3 MB),
  útiles para el documento del trabajo de grado.
- Rótulo «Datos sintéticos» también en la cabecera móvil (el sidebar no se ve en móvil).
- La barra del año 0 del flujo es su propia serie («Inversión inicial») para que la leyenda
  muestre su color.
- **Contrato de la API ampliado (misma causa, OT-0005):** `parametros` (kWp, kWh de batería,
  pérdida térmica %/°C, error de predicción 3–8 %, umbrales del detector 30 % / 2 kWh). Los
  textos de la UI los leen de ahí en vez de copiarlos: una sola fuente (cabecera del seeder y
  `analitica/services.py`).
- **Aviso cuando un CDN no carga** (script en línea en `base.html`, sin depender de ningún CDN)
  y retiro del componente si falta Chart.js. Motivo medido: en una corrida, la red del WSL cortó
  los CDN (`net::ERR_NETWORK_CHANGED`) y la página quedó rota en silencio con 115 errores en
  cascada. Relevante para una ZNI con conectividad precaria (ver §8).

## 4. Diseño / enfoque técnico
- **CDN con versión exacta fijada** (se anotan en la bitácora): Tailwind Play CDN, Alpine.js 3.x,
  Chart.js 4.x, Lucide. **Sin** plugins de Chart.js extra: las bandas de umbral y la marca del
  payback se dibujan con un plugin *inline* pequeño (menos dependencias).
- **Paleta semántica (`CLAUDE.md` §3)**: esmeralda = generación/óptimo, ámbar =
  irradiancia/alerta, índigo = demanda, rojo = crítico/anomalía; segmentos con 4 tonos
  distinguibles. Colores en **un solo objeto JS** de tokens, reutilizado por todos los gráficos.
- **Alpine:** un `x-data="dashboard()"` con `rango`, `pestana`, `datos`, `cargando`, `error`.
  Cambiar rango = **un** `fetch`; cambiar pestaña = sin red.
- **Trampa conocida de Chart.js:** un canvas dentro de un contenedor `display:none` (pestaña
  oculta con `x-show`) se crea con tamaño 0. Enfoque: los gráficos de una pestaña se
  **crean la primera vez que se muestra** y se **actualizan** (`chart.data = …; update()`) al
  cambiar el rango, en lugar de destruirlos y recrearlos. Se registran en un mapa por id para
  no duplicar instancias (fuente típica del error «Canvas is already in use»).
- Eje X: etiquetas formateadas (`dd/MM HH:mm`) como categorías; sin adaptador de fechas.
- Formato `es-CO` con `Intl.NumberFormat` (COP sin decimales, kWh con 1).
- Navegación responsive: sidebar fijo en escritorio; en móvil, barra superior con menú.
- Guía visual: se consulta la skill `dataviz` antes de escribir el primer gráfico.

### Decisiones de diseño tomadas al ejecutar
- **Doble eje Y — se mantiene por especificación del lead.** La skill `dataviz` lo desaconseja
  (dos escalas en un gráfico se leen mal), pero el plan pide explícitamente «Generación FV vs.
  Irradiancia» y «Generación vs. Demanda vs. SoC» en un gráfico. Mitigación: títulos de eje con
  unidad, la serie del eje derecho con otro tipo de marca (línea sobre barras o discontinua) y
  tooltip con ambas magnitudes. Alternativa si el lead la prefiere: dos gráficos apilados con el
  mismo eje X.
- **Paleta validada con `validate_palette.js` (skill `dataviz`) en Chromium, sobre fondo blanco:**
  Resumen esmeralda/índigo/cielo → pasa (CVD ΔE 10,6; normal 16,1); Temperaturas cielo/naranja
  → pasa (23,4 / 33,3); FV esmeralda/ámbar → CVD 7,9 (banda 6–8, legal sólo con codificación
  secundaria: generación en barras, irradiancia en línea); segmentos índigo/teal/naranja/rosa →
  pasa (13,1 / 15,4). Rechazadas: índigo/cian/rosa/pizarra (pizarra con croma 0,041, se lee
  gris) e índigo/naranja/teal/rosa (CVD 3,8 entre rosa y teal).
- **Sin animaciones en Chart.js** (`Chart.defaults.animation = false`), ver bitácora.
- `[x-cloak] { display: none !important; }`: es la receta oficial de Alpine; sin `!important`,
  las clases de Tailwind (`flex`, `grid`) del mismo elemento ganan por orden y el contenido
  parpadea antes de que Alpine arranque. Única excepción a la regla de no usar `!important`.

## 5. Plan por fases
- [x] **Fase 1 —** `base.html` + layout (sidebar, cabecera, selector de rango, 6 pestañas vacías) + store de Alpine + `fetch` con estados de carga/error/vacío.
- [x] **Fase 2 —** Tokens de color + fábrica de gráficos (crear perezoso / actualizar) + plugin inline de bandas y marcas.
- [x] **Fase 3 —** Pestaña 1 (Resumen) y 2 (FV).
- [x] **Fase 4 —** Pestaña 3 (Demanda) y 4 (Almacenamiento).
- [x] **Fase 5 —** Pestaña 5 (Analítica) y 6 (Financiero).
- [x] **Fase 6 —** Pulido responsive y accesibilidad (contraste, `aria` en pestañas), prueba de la vista (`/` → 200 y contiene los 6 módulos), `verify`, validador, commit. Capturas en la bitácora si hay navegador sin cabeza disponible.

## 6. Criterios de aceptación
- [x] Las 6 pestañas muestran datos en los 3 rangos; cambiar de rango actualiza todas.
- [~] Cero errores en la consola del navegador — medido en las capturas (sólo el aviso aceptado de Tailwind); la verificación formal con control negativo es de OT-0007.
- [x] Bandas de SoC y marca de payback visibles; anomalías resaltadas en rojo.
- [x] Sin scroll horizontal a 390 px.
- [x] `verify` en verde.

## 7. Checklist de cumplimiento
Tailwind/Alpine/Chart.js **por CDN** (`CLAUDE.md` §3) · Inter · `border-slate-200` + `shadow-sm`
· paleta semántica · sin `console.log` de depuración · sin `setTimeout` para forzar el DOM.

## 8. Riesgos y rollback
- **Riesgo:** el Play CDN de Tailwind avisa en consola que no es para producción. → Es la
  herramienta que exige `CLAUDE.md`; en OT-0007 se distingue ese *warning* (esperado) de
  errores reales. **Resuelto (2026-10-28):** el lead acepta el aviso como esperado; sin Node
  ni compilación de CSS en esta fase (entorno 100 % Python/Django).
- **Riesgo (para el despliegue real en Amalfi):** el dashboard depende de 4 CDN; sin internet
  sólo muestra el aviso. `CLAUDE.md` exige CDN en el MVP; para operar en la ZNI convendría
  servir las librerías desde `static/` (OT futura, decisión del lead).
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | **Implementado:** `base.html` (CDN fijados: Tailwind 3.4.16, Chart.js 4.4.7, Lucide 0.469.0, Alpine 3.14.8; Inter), `dashboard.html` (sidebar + navegación móvil renderizadas por el servidor desde `views.PESTANAS`, selector de rango, 6 paneles con `x-show`, estados de carga/error/vacío) y `static/monitoreo/dashboard.js` (store de Alpine, gráficos fuera del Proxy, creación perezosa + actualización, plugins *inline* de bandas y marca vertical, formato es-CO leyendo la hora del texto ISO para mostrar siempre hora de Amalfi, contador de peticiones que descarta respuestas tardías, `AbortSignal.timeout(15 s)`). URLs de CDN comprobadas con `curl` (200) e íconos de Lucide comprobados en el bundle. |
| 2026-10-28 | — | **Revisión visual con capturas (Chromium sin cabeza):** encontrados y corregidos: puntos de leyenda huecos en series de línea; eje de irradiancia hasta 1 100 con «1.000/1.100» encimados (→ tope 1 000); etiquetas del eje X encimadas en gráficos de media anchura (→ `autoSkipPadding`); unidad «kWh/h» (→ kW, potencia media de la hora pico); texto falso en la tarjeta de payback («incluye el reemplazo del año 10», cuando el payback de 7 años llega antes) → corregido; rótulo de datos sintéticos ausente en móvil; plantillas cacheadas por `runserver --noreload` (las capturas móviles iniciales eran de la plantilla vieja). |
| 2026-10-28 | — | **Gráficos de Almacenamiento cortados (SoC y potencia sólo hasta el 23/10).** No se reprodujo: con clic real (y también repitiendo el flujo de la captura) los puntos están en su sitio desde los 50–300 ms (`lastX` = ancho del área). **Mecanismo no establecido**; lo único medido es que a los 100 ms las barras aún tienen altura 0 (animación inicial). Mitigación: animaciones desactivadas — con 720 puntos no aportan y así ninguna captura o impresión sale a medio dibujar. |
| 2026-10-28 | — | **Medido en Chromium:** tras crear todos los gráficos con 7 días, cambiar a 30 d / 24 h / 7 d deja **todas** las series con 720 / 24 / 168 puntos (flujo 26, dona 4); `pageerror`: ninguno. Capturas a 1 440 px (7 y 30 días) y 390 px (24 h y 7 días): sin scroll horizontal; única salida de consola: el aviso aceptado de Tailwind. |
| 2026-10-28 | — | **`verify`: `Ran 105 tests … OK`** (+5: 6 paneles con su pestaña, 4 scripts de CDN con versión exacta, rótulo de datos sintéticos, URL de la API desde el router, y sincronía pestañas (Python) ↔ gráficos (JS) ↔ `<canvas>` (HTML)). **Control negativo:** quitar `g-potencia` de `GRAFICOS_POR_PESTANA` en el JS ⇒ FAIL; restaurado ⇒ OK. |
| 2026-10-28 | — | **Validador (subagente, Chromium con zona `Asia/Tokyo` y `en-US`): ⚠️ aprobar con menores.** Reprodujo las cifras de la UI contra el JSON (6 324 / 4 855 kWh, $ 13 919 425, 3,71 t, 546/94/80 h, pico 21,3 kW, 44,6/30,1/14,2/11,1 %, MAE 1,26, R² 0,928/0,978, 8 anomalías, CAPEX/VPN/TIR/LCOE/payback); horas en hora de Amalfi aun con el navegador en Tokio; `Chart.instances` estable en 10 tras 54 cambios; carreras de peticiones resueltas al último rango; 4 tipos de error con «Reintentar» funcional; sin scroll horizontal a 390/1 440. **Hallazgos atendidos:** (1, medio) **`pageerror` con base vacía** (`d && f.num(k.demanda_kwh…)` no protege con `kpis: null`) → guarda `k &&`; (2) tras un error quedaban datos de un rango con el botón de otro → el selector vuelve al rango mostrado, y un 500 en HTML ya no muestra «Unexpected token '<'»; (3) «Supera la tasa» fijo → condicional; constantes copiadas en textos (50 kWp, 120 kWh, 3–8 %, 30 %, 2 kWh, 0,4 %) → `parametros` de la API; (4) contraste del selector 4,34:1 → `slate-600`; pestañas con patrón WAI-ARIA (`tabindex` móvil, flechas, `id` en la barra móvil); (5) rótulos del SoC tachados por la serie → se dibujan después de los datos, con fondo; temperatura ambiente discontinua (identidad no sólo por color); (6) `hashchange` → atrás/adelante cambian de pestaña. |
| 2026-10-28 | — | **Medido tras las correcciones (Chromium):** base vacía en las 6 pestañas → 0 `pageerror` y mensaje visible; 500 en HTML al pedir 30 d → «El servidor respondió con un error (HTTP 500).» y selector de vuelta en 7 d; teclado: ↓↓ desde Resumen → Demanda con foco y `tabindex` 0/−1, ↑×3 cicla a Financiero; historial: atrás → Resumen, adelante → Financiero. **CDN bloqueados uno a uno** (Chart.js, Alpine, Lucide, Tailwind): aviso visible y **0 `pageerror`** en los cuatro (antes de retirar el componente, sin Chart.js daba 115). Un bug propio cazado al probar: `evento.currentTarget` es `null` dentro de `$nextTick` → se captura antes. `verify`: `Ran 106 tests … OK` (+1: `parametros` de la API). Capturas de `docs/capturas/` regeneradas. |
| 2026-10-28 | 0902c32 | **Cierre:** commit(s) de la OT; visto bueno del lead y merge *fast-forward* a `main`. (Las filas anteriores llevan «—» porque se escribieron antes del commit; el SHA de la OT es éste.) |
