---
id: OT-0007
tipo: chore
titulo: "Verificación integral del MVP (Django, datos, API y consola del navegador)"
rama: "chore/ot-0007-verificacion-mvp"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: [OT-0006]
docs_ref: [CLAUDE.md, ordenes-de-trabajo/00-README.md]
creado: 2026-10-28
---

# OT-0007 — Verificación integral del MVP

## 1. Contexto y problema
Cada OT verifica lo suyo; falta comprobar que **el conjunto** funciona desde un clon limpio y
que el navegador no registra errores (punto 6 del plan).

## 2. Objetivo
Desde una base vacía, `uv sync` → `migrate` → `seed_amalfi_data` → `runserver` deja un
dashboard con las 6 pestañas pobladas en los 3 rangos y **cero errores** en la consola del
navegador, con la evidencia anotada.

## 3. Alcance
**Qué SÍ entra:**
- Recorrido completo desde base vacía (borrar `db.sqlite3`).
- `manage.py check` y `check --deploy` (este último **informativo**: el MVP es local; se listan
  los avisos y se justifican, no se «arreglan» a ciegas).
- Pruebas completas + `curl` a la API en los 3 rangos y con parámetros inválidos.
- **Consola del navegador** con Playwright (Chromium sin cabeza, como dependencia **de
  desarrollo**): abre `/`, recorre las 6 pestañas × 3 rangos, recoge `console.error`,
  `pageerror` y peticiones fallidas, y guarda capturas.
- README del repo: cómo levantar el proyecto en 4 comandos.
- Corrección de lo que aparezca (regla de raíz: si es del mismo MVP, se arregla aquí y se anota).

**Qué NO entra:** despliegue a un servidor; CI remoto.

**Alcance ampliado durante la ejecución:**
- El script verifica más que la consola: que cada gráfico visible tenga los puntos del rango
  (24/168/720), que no haya scroll horizontal y que no haya respuestas HTTP ≥ 400; y corre en
  escritorio (1 440 px) **y** móvil (390 px): 2 × 3 rangos × 6 pestañas = 36 combinaciones.
- El control negativo cubre los tres canales (error de JS, aviso de consola y 404), no sólo uno.
- `scripts/verificar_consola.py` levanta su propio `runserver` en un puerto libre y usa solo las
  librerías de Chromium extraídas sin `sudo` si existen; el README lo explica.

## 4. Diseño / enfoque técnico
- Script `scripts/verificar_consola.py` (Playwright) — reproducible, no un clic manual.
- **Única excepción permitida:** el aviso del Play CDN de Tailwind («should not be used in
  production»), aceptado por el lead (2026-10-28). Se filtra por su texto exacto, no por nivel,
  para que cualquier otro aviso o error sí cuente.
- **Control negativo:** el script debe **fallar** si se inyecta un error de JS a propósito;
  si no falla, no está midiendo nada (bóveda: *Framework_Evidencia_Medida_vs_Afirmada*).
- **Playwright y Chromium ya están instalados** (adelantados en OT-0006): en este WSL Chromium
  necesita `LD_LIBRARY_PATH=~/.cache/sun-ia-chromium-deps/root/usr/lib/x86_64-linux-gnu`
  (librerías extraídas sin `sudo`); el script y el README deben resolverlo, o documentar
  `sudo uv run playwright install-deps` como alternativa.
- Si Chromium no puede correr en este WSL, plan B: el lead abre el dashboard en Windows
  (`http://localhost:8000`) con DevTools y se anota su resultado.

## 5. Plan por fases
- [x] **Fase 1 —** Recorrido desde base vacía + `check`, `check --deploy`, pruebas, `curl`.
- [x] **Fase 2 —** Script de consola con Playwright + control negativo.
- [x] **Fase 3 —** Corregir hallazgos; capturas de las 6 pestañas.
- [x] **Fase 4 —** README; validador final sobre todo el MVP; commit; estado de todas las OT a «Hecho» con visto bueno del lead.

## 6. Criterios de aceptación
- [x] `check` sin issues; avisos de `--deploy` listados y justificados.
- [x] Todas las pruebas en verde (número de pruebas en la bitácora).
- [x] 0 `console.error` / `pageerror` / peticiones fallidas en 6 × 3 combinaciones (salida del script).
- [x] El control negativo hace fallar el script.
- [x] README probado siguiendo sus propios pasos.

## 7. Checklist de cumplimiento
Playwright sólo como dependencia de desarrollo · sin secretos · capturas sin datos reales (son sintéticos).

## 8. Riesgos y rollback
- **Riesgo:** descargar Chromium requiere red y ~150 MB. → Plan B en §4.
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | **Recorrido desde base vacía (medido):** `rm db.sqlite3` → `migrate` (21 migraciones OK) → `seed_amalfi_data` → `check`: `no issues`. `check --deploy` con `DJANGO_DEBUG=0`: **5 avisos, todos esperados en un MVP local sin HTTPS**: W004 `SECURE_HSTS_SECONDS`, W008 `SECURE_SSL_REDIRECT`, W012 `SESSION_COOKIE_SECURE`, W016 `CSRF_COOKIE_SECURE` (los cuatro exigen servir por HTTPS: se configuran al desplegar) y W009 `SECRET_KEY` (es el valor de desarrollo a propósito; fuera de local se define `DJANGO_SECRET_KEY`, OT-0002). Con `DEBUG=1` aparece además W018, también esperado. |
| 2026-10-28 | — | **Pruebas y API:** `verify` → `Ran 106 tests … OK`. `curl`: `dias=1/7/30` → 24/168/720 registros (8,2 / 24,8 / 88,3 KB); `dias=abc`, `desde>hasta`, `hasta=9999-12-31` → 400 con mensaje; `/` → 200; `/admin/` → 302 (login). |
| 2026-10-28 | — | **Observación:** al re-sembrar una hora más tarde, la ventana pasó a 2026-09-28 16:00 → 2026-10-28 15:00 y las cifras del mes cambiaron un poco (generación 6 278 vs. 6 324 kWh; CRITICO 87 vs. 80 h; no suministrada 226 vs. 216). Es el diseño (la ventana termina en la hora actual y los perfiles dependen de la hora local); la semilla reproduce los datos sólo con la misma hora de inicio. Los indicadores financieros no cambian. Documentado en el README y elevado al lead (¿fijar una fecha de cierre para que las cifras del documento escrito sean estables?). |
| 2026-10-28 | — | **`scripts/verificar_consola.py`:** 36 combinaciones (escritorio y móvil × 3 rangos × 6 pestañas) → `OK`, código 0, ~11 s. **Control negativo** (`--control-negativo`) → código 1 con `console.warning: control negativo: aviso`, `pageerror: control negativo: error`, `HTTP 404 …/no-existe-control-negativo` y su `console.error` asociado, en ambas ventanas. La comprobación de puntos por gráfico también quedó probada sin querer: la primera versión del script leía `n_registros` antes de que Alpine guardara la respuesta y reportó «720 puntos, se esperaban 168» → se espera a que el rango cargado sea el pedido. |
| 2026-10-28 | — | **README probado siguiendo sus pasos** en una copia limpia del repo (`git ls-files` → carpeta nueva, sin `.venv` ni base): `uv sync` → `migrate` → `seed_amalfi_data` → `runserver`: `/` 200 y API 30 d con 720 registros y TIR 14,49 %; en la copia, `verify` → 106 OK y `verificar_consola.py` → OK. (Trampa de la bóveda reproducida: un `pkill -f "[r]unserver …:8123"` mató a su propio shell porque la línea del shell contenía el patrón sin corchetes; el servidor se detiene por PID.) |
| 2026-10-28 | — | **Validador final (subagente, todo el MVP): ⚠️ aprobar con menores.** Encargo cumplido de punta a punta (5 modelos exactos; 720 h; SoC 15–100 %; segmentos = total en 720/720 h; 8 anomalías; error 3,0–8,0 % en las 353 horas diurnas normales; TIR 14,49 %, VPN 227,9 M, año 10 = 152,5 M; API 200/400; 6 pestañas sin NaN/undefined) y cifras financieras reproducidas exactas. **Hallazgos medios sobre el script:** (1) **pasaba en verde con el dashboard vacío** (series y KPIs a `null`: sólo contaba `labels.length`), contra lo que prometían el docstring y el README; (2) **pasaba con 0 pestañas** (sin `role="tab"`): el recuento sólo se imprimía. Menores: control negativo sin mutante de datos; servidor no se mataba si `wait` vencía; README sin decir desde qué carpeta; `libasound2t64` sólo en Ubuntu 24.04; columnas SHA en «—»; visto bueno del lead no anotado en OT-0002/0003/0005/0006. |
| 2026-10-28 | — | **Correcciones (medido):** el script exige 6 pestañas y 3 rangos, cuenta **valores numéricos distintos de cero** por gráfico y busca «—», «NaN», «undefined» en el panel visible; `kill` si el servidor no termina. Control negativo ampliado con la API vaciada → código 1 con los **5 canales**: `console.warning` 2, `pageerror` 2, `HTTP 404` 2, «sin valores» 36, «valor vacío» 24 (68 problemas). Mutante del validador (HTML sin `role="tab"`) → «0 pestañas visibles, se esperaban 6». Corrida normal → OK, código 0 (sin falsos positivos de las comprobaciones nuevas). README: carpeta de cada comando y `libasound2` en 22.04. Bitácoras de OT-0002…0006 con fila de cierre (SHA + visto bueno + merge). |
| 2026-10-28 | — | **Riesgos residuales para el lead:** (a) las cifras del mes dependen de la hora de siembra (pregunta abierta: ¿fecha de cierre fija?); (b) 4 CDN: sin internet sólo se ve el aviso, y la red del WSL es inestable — el validador vio un falso positivo del script por `ERR_NETWORK_CHANGED` en Google Fonts (si el script falla con `requestfailed` a un CDN, repetir antes de buscar un bug). |
