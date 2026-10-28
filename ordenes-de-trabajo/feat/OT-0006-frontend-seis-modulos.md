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
  | 6 | Financiero | Tarjetas CAPEX, OPEX, VPN, TIR, LCOE · barras (flujo neto) + línea (acumulado) a 25 años con **marca del payback** |
- Rótulo visible «Datos sintéticos — caso de estudio» (ADR-0001).
- Estados de carga, error y base vacía.

**Qué NO entra:** cambios al contrato de la API (si algo falta, se amplía OT-0005 por regla de
raíz y se anota aquí); modo oscuro; recálculo financiero interactivo (`CLAUDE.md` §2).

**Alcance ampliado durante la ejecución:** _(vacío)_

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

## 5. Plan por fases
- [ ] **Fase 1 —** `base.html` + layout (sidebar, cabecera, selector de rango, 6 pestañas vacías) + store de Alpine + `fetch` con estados de carga/error/vacío.
- [ ] **Fase 2 —** Tokens de color + fábrica de gráficos (crear perezoso / actualizar) + plugin inline de bandas y marcas.
- [ ] **Fase 3 —** Pestaña 1 (Resumen) y 2 (FV).
- [ ] **Fase 4 —** Pestaña 3 (Demanda) y 4 (Almacenamiento).
- [ ] **Fase 5 —** Pestaña 5 (Analítica) y 6 (Financiero).
- [ ] **Fase 6 —** Pulido responsive y accesibilidad (contraste, `aria` en pestañas), prueba de la vista (`/` → 200 y contiene los 6 módulos), `verify`, validador, commit. Capturas en la bitácora si hay navegador sin cabeza disponible.

## 6. Criterios de aceptación
- [ ] Las 6 pestañas muestran datos en los 3 rangos; cambiar de rango actualiza todas.
- [ ] Cero errores en la consola del navegador (verificado en OT-0007).
- [ ] Bandas de SoC y marca de payback visibles; anomalías resaltadas en rojo.
- [ ] Sin scroll horizontal a 390 px.
- [ ] `verify` en verde.

## 7. Checklist de cumplimiento
Tailwind/Alpine/Chart.js **por CDN** (`CLAUDE.md` §3) · Inter · `border-slate-200` + `shadow-sm`
· paleta semántica · sin `console.log` de depuración · sin `setTimeout` para forzar el DOM.

## 8. Riesgos y rollback
- **Riesgo:** el Play CDN de Tailwind avisa en consola que no es para producción. → Es la
  herramienta que exige `CLAUDE.md`; en OT-0007 se distingue ese *warning* (esperado) de
  errores reales. **Pregunta abierta:** ¿aceptas ese aviso o prefieres compilar Tailwind?
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
