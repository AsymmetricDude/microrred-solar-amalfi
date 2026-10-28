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

**Alcance ampliado durante la ejecución:** _(vacío)_

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
- [ ] **Fase 1 —** Recorrido desde base vacía + `check`, `check --deploy`, pruebas, `curl`.
- [ ] **Fase 2 —** Script de consola con Playwright + control negativo.
- [ ] **Fase 3 —** Corregir hallazgos; capturas de las 6 pestañas.
- [ ] **Fase 4 —** README; validador final sobre todo el MVP; commit; estado de todas las OT a «Hecho» con visto bueno del lead.

## 6. Criterios de aceptación
- [ ] `check` sin issues; avisos de `--deploy` listados y justificados.
- [ ] Todas las pruebas en verde (número de pruebas en la bitácora).
- [ ] 0 `console.error` / `pageerror` / peticiones fallidas en 6 × 3 combinaciones (salida del script).
- [ ] El control negativo hace fallar el script.
- [ ] README probado siguiendo sus propios pasos.

## 7. Checklist de cumplimiento
Playwright sólo como dependencia de desarrollo · sin secretos · capturas sin datos reales (son sintéticos).

## 8. Riesgos y rollback
- **Riesgo:** descargar Chromium requiere red y ~150 MB. → Plan B en §4.
- **Rollback:** borrar la rama.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
