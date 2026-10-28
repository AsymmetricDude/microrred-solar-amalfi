---
id: OT-0008
tipo: feat
titulo: "Reproducibilidad de fechas y modo offline ZNI"
rama: "feat/ot-0008-reproducibilidad-offline"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: [OT-0007]
docs_ref: [CLAUDE.md, ordenes-de-trabajo/chore/OT-0007-verificacion-integral-mvp.md]
creado: 2026-10-28
---

# OT-0008 — Reproducibilidad de fechas y modo offline ZNI

> El estado NO se escribe aquí: vive en la columna «Estado» del índice (`00-README.md`).

## 1. Contexto y problema
OT-0007 dejó dos riesgos abiertos, que el lead decide cerrar para la sustentación:
1. **Las cifras del mes dependen de la hora de siembra**: la ventana termina en la hora actual, así
   que re-sembrar cambia energías y horas por estado (medido: CRITICO 80 → 87 h). El documento
   escrito y el dashboard pueden no coincidir.
2. **El dashboard depende de 4 CDN y de Google Fonts**: sin internet —lo normal en una ZNI— sólo
   muestra el aviso de librerías faltantes.

## 2. Objetivo
`seed_amalfi_data` sin argumentos reproduce **exactamente** las cifras de la bitácora de OT-0004
(ventana 2026-09-28 15:00 → 2026-10-28 14:00), y el dashboard renderiza intacto con **toda petición
externa bloqueada**, verificado con Playwright.

## 3. Alcance
**Qué SÍ entra:**
- `FECHA_FIN_DEFAULT = 2026-10-28 14:00` (hora de Bogotá) en la cabecera del seeder y argumento
  opcional `--hasta` (ISO 8601). Prueba que fija las cifras de la bitácora.
- Tailwind (Play CDN 3.4.16), Chart.js 4.4.7, Alpine.js 3.14.8, Lucide 0.469.0 e Inter (variable,
  latin) en `monitoreo/static/vendor/`, servidos con `{% static %}`.
- Manifiesto de lo vendorizado (versión, URL de origen, SHA-256, licencia) y prueba que lo verifica.
- `scripts/verificar_consola.py --offline`: bloquea toda petición que no sea al servidor local y
  falla si la página intenta alguna.
- README y bitácoras.

**Qué NO entra:** compilar Tailwind (el lead descartó pasos de compilación de CSS, 2026-10-28): se
vendoriza el mismo script del Play CDN, que genera el CSS en el navegador, y su aviso de consola
sigue siendo el único permitido. Despliegue con `DEBUG=0` (`collectstatic`/servidor web).

**Alcance ampliado durante la ejecución:**
- **`CLAUDE.md` §3** decía «vía CDN»: se actualiza con la decisión del lead y se registra en
  [ADR-0003](../../docs/adr/ADR-0003-frontend-sin-internet.md) (las reglas del producto no pueden
  contradecir el código).
- **Bug encontrado al mirar la captura sin red:** un comentario `{# … #}` de dos líneas en
  `base.html` se imprimía como texto arriba de la página (Django sólo admite `{# #}` de una línea).
  Ni las pruebas ni el verificador lo vieron: pasaron en verde. Se corrigió con `{% comment %}` y
  se cerró la brecha en los dos lados: prueba de que el HTML no contiene `{#`/`#}`, y el verificador
  busca restos de plantilla (`{#`, `#}`, `{{`, `{%`) en **todo** el texto visible.
- El aviso de librerías faltantes ya no dice «revisa la conexión a internet» (ahora son locales):
  apunta a `/static/`.

## 4. Diseño / enfoque técnico
- **`--hasta`** es la **última hora** de la ventana (inclusiva), igual que el último registro que
  hoy produce la siembra. Sin zona → hora de Bogotá; con zona → se convierte. Se trunca a la hora en
  punto. `--dias` sigue funcionando con él.
- **Prueba de reproducibilidad con cifras**: sembrar sin argumentos y comparar contra la bitácora
  de OT-0004 (546/94/80 h; 6 324 / 4 855 / 1 521 / 216 kWh; 8 anomalías; TIR 14,49 %). Si la
  autora cambia un supuesto, esta prueba avisa que el documento escrito también debe cambiar.
- **Versión en la ruta** (`vendor/chartjs/4.4.7/chart.umd.min.js`): la versión se ve en la plantilla
  y en el repo, como antes en la URL del CDN.
- **`vendor/MANIFIESTO.json`** con versión, origen, SHA-256 y licencia de cada archivo; una prueba
  recalcula los SHA-256 (un archivo tocado a mano falla) y otra exige que la plantilla no cite
  **ninguna URL externa**.
- **Inter** desde `@fontsource-variable/inter` 5.3.0 (OFL-1.1): un `woff2` variable (pesos
  100–900) del subconjunto latin, con su `@font-face` en `vendor/inter/inter.css`.

## 5. Plan por fases
- [x] **Fase 0 —** Decisiones del lead (2026-10-28): fecha fija 2026-10-28 14:00 + `--hasta`; todo
      local en `static/vendor/`, sin compilar CSS; verificar con Playwright sin red.
- [x] **Fase 1 —** Seeder: `FECHA_FIN_DEFAULT`, `--hasta`, pruebas (cifras de la bitácora, `--hasta`
      con y sin zona, inválido → error).
- [x] **Fase 2 —** Descarga a `static/vendor/` + manifiesto + licencias.
- [x] **Fase 3 —** `base.html` con `{% static %}`, sin Google Fonts; pruebas del manifiesto y de
      «ninguna URL externa».
- [x] **Fase 4 —** `verificar_consola.py --offline` + control negativo (una petición externa a
      propósito debe fallar); corrida normal y offline.
- [x] **Fase 5 —** README, `verify`, validador, commit.

## 6. Criterios de aceptación
- [x] `seed_amalfi_data` sin argumentos → ventana 2026-09-28 15:00 → 2026-10-28 14:00 y las cifras
      de la bitácora de OT-0004, dos veces seguidas y a horas distintas.
- [x] `--hasta` desplaza la ventana; un `--hasta` inválido es `CommandError`.
- [x] `verificar_consola.py --offline` → OK con toda petición externa bloqueada; su control
      negativo falla.
- [x] La plantilla no contiene URLs externas; los SHA-256 del manifiesto cuadran.
- [x] `verify` en verde.

## 7. Checklist de cumplimiento
Licencias de terceros incluidas (MIT, ISC, OFL-1.1) · versiones exactas, las mismas que ya se
usaban · sin cambios en la UI más allá del origen de los archivos.

## 8. Riesgos y rollback
- **Riesgo:** con la fecha fija, «últimas 24 h» ya no son las de hoy. → Es el objetivo (cifras del
  documento escrito); la API ya ancla los rangos al último registro (OT-0005).
- **Riesgo:** ~1,1 MB de JS de terceros en el repo. → Aceptable a cambio de operar sin internet;
  el manifiesto deja su origen auditable.
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | **Fase 1 — seeder (medido):** `FECHA_FIN_DEFAULT = "2026-10-28T14:00"` y `--hasta` con gramática ASCII explícita (no `fromisoformat` a secas: acepta más de lo documentado). El seeder ya no lee el reloj (`grep` de `localtime()`/`now`: vacío). Dos siembras seguidas → salida idéntica: ventana 2026-09-28 15:00 → 2026-10-28 14:00; 6 324 / 4 855 / 1 521 / 216 kWh; 546/94/80 h; 8 anomalías — **las cifras de la bitácora de OT-0004**, ahora fijadas por la prueba `test_sin_argumentos_reproduce_las_cifras_de_la_bitacora`. `--hasta "2026-10-01 10:00" --dias 14` → 2026-09-17 11:00 → 2026-10-01 10:00; `--hasta ayer` → `CommandError` sin borrar datos; con zona `+00:00` se convierte y se trunca a la hora. |
| 2026-10-28 | — | **Fase 2 — vendor:** descargadas las mismas versiones que se usaban por CDN (Tailwind 3.4.16 451 131 B, Chart.js 4.4.7 205 889 B, Alpine 3.14.8 44 758 B, Lucide 0.469.0 358 106 B) e Inter variable latin (`@fontsource-variable/inter` 5.3.0, 48 256 B, publicada 2026-07-19). Licencias: MIT ×3, ISC, OFL-1.1; la de Alpine no viene en su paquete npm y se tomó de su repositorio en el tag `v3.14.8`. `MANIFIESTO.json` con SHA-256. Total ~1,1 MB. El script de Tailwind sólo contiene URLs de documentación (no descarga nada en ejecución: confirmado en la Fase 4). |
| 2026-10-28 | — | **Fase 3 — plantilla y pruebas:** `base.html` con `{% static %}`, sin Google Fonts. Pruebas nuevas: ninguna URL externa en el HTML; las 5 rutas locales están en el manifiesto y llevan versión; SHA-256 de cada archivo; cada archivo con licencia; nada sin declarar en `vendor/`. **Controles negativos:** un byte añadido a Alpine → FAIL `sha256 … alpinejs/3.14.8/cdn.min.js` (restaurado, mismo md5); Google Fonts de vuelta en la plantilla → FAIL en las dos pruebas de la plantilla. |
| 2026-10-28 | — | **Fase 4 — sin internet (medido en Chromium):** `verificar_consola.py --offline` (aborta todo host que no sea el servidor local) → **OK, código 0, 36 combinaciones**; corrida normal → OK. En la página sin red: `document.fonts` → `Inter:loaded`, `document.fonts.check('16px Inter')` → `true`, peticiones externas intentadas → **ninguna**. Control negativo con `--offline` → código 1 con «petición externa bloqueada: https://example.com/control-negativo» más los 5 canales de siempre (72 problemas). Mutante del comentario de varias líneas → el verificador reporta «resto de plantilla «{#»/«#}» visible»; restaurado → OK. `verify`: `Ran 115 tests … OK`. |
| 2026-10-28 | — | **Validador (subagente): ⚠️ aprobar con menores, nada bloquea.** Midió: dos siembras en una copia → mismas cifras que la bitácora de OT-0004; ningún camino lee el reloj (seeder, API, JS, pruebas); mutante `FECHA_FIN_DEFAULT` a las 20:00 → 2 pruebas FAIL; `--hasta` con `Z`, `+05:30`, segundos, `24:00`, `:60`, `\n`, `t` minúscula → correcto o `CommandError`; mutantes offline (`@import` de Google Fonts, `fetch` externo, `<img>` y `url()` externos) → todos detectados; **los 5 orígenes sirven hoy exactamente los SHA-256 del manifiesto** y las licencias son idénticas a las originales; Tailwind no hace peticiones en ejecución. **Hallazgos atendidos:** (1) `chart.umd.min.js` no existe en el paquete npm: lo genera el CDN al vuelo («Do NOT use SRI with dynamically generated files») → se vendoriza `dist/chart.umd.js`, el archivo real (205 615 B, sha `2812cb88…`), y el manifiesto lo explica; (2) `--offline` sólo admitía 127.0.0.1/localhost → también el host de `--url`; (3) la prueba de URLs externas no veía `//host` ni `url(…)` → ampliada; (6) comentario «CDN inaccesible» en `dashboard.js`; (7) 1,2 MB → ~1,1 MB (1 119 535 B con `du -sb`); (8) `--hasta 0001-01-01T00:00` daba `OverflowError` con traceback → `CommandError`, con caso en la prueba; (9) la prueba de cifras fija ahora también los segmentos (2 165 / 1 462 / 689 / 540 kWh), el VPN (227 919 781) y el LCOE (3 173,35). **Informativos, sin cambio:** →, ₂ y ≥ caen fuera del subconjunto latin de Inter y se dibujan con la fuente del sistema (igual que con Google Fonts antes: no es regresión); Chart.js y Lucide citan `.map` no vendorizados (404 local sólo con DevTools abierto; quitar la línea cambiaría el SHA-256 frente al origen). El validador escribió por error 13 descargas en la raíz del repo y las movió al scratchpad; `git status` comprobado limpio después. |
| 2026-10-28 | — | **Tras las correcciones:** `verify` → `Ran 115 tests … OK`; `verificar_consola.py --offline` → OK (servidor propio y con `--url http://127.0.0.1:8765/`); `seed_amalfi_data --hasta 0001-01-01T00:00` → «CommandError: --hasta fuera del rango admitido». |
