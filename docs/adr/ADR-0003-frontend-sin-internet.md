---
id: ADR-0003
titulo: "Las librerías del frontend se sirven localmente, sin CDN"
estado: aceptada
fecha: 2026-10-28
supersede: ""
tags: [adr, decision, frontend, offline, zni]
---

# ADR-0003 — Las librerías del frontend se sirven localmente, sin CDN

## Contexto

- `CLAUDE.md` pedía Tailwind, Alpine.js y Chart.js **por CDN** (y Lucide e Inter salían de
  terceros), sin paso de compilación de CSS.
- El sistema es para una **Zona No Interconectada**: sin internet garantizado. Medido en OT-0007:
  con los CDN inaccesibles, la página sólo muestra un aviso de librerías faltantes.
- El lead decidió (2026-10-28, OT-0008) operar 100 % sin internet, **manteniendo** el entorno
  «sólo Python/Django», sin Node ni compilación.

## Decisión

- Las **mismas versiones exactas** que se usaban por CDN (Tailwind Play 3.4.16, Chart.js 4.4.7,
  Alpine.js 3.14.8, Lucide 0.469.0) más Inter variable (latin, `@fontsource-variable/inter`
  5.3.0) se versionan en `monitoreo/static/vendor/<librería>/<versión>/` y se sirven con
  `{% static %}`.
- `vendor/MANIFIESTO.json` registra versión, origen, SHA-256 y licencia de cada archivo; las
  licencias (MIT, ISC, OFL-1.1) van en `vendor/licencias/`. Las pruebas recalculan los SHA-256,
  exigen que no haya archivos sin declarar y que la plantilla no cite ninguna URL externa.
- **Tailwind sigue siendo el script del Play CDN**, que genera el CSS en el navegador: compilarlo
  exigiría un paso de construcción que el lead descartó. Su aviso de consola («should not be used
  in production») sigue siendo el único permitido.

## Consecuencias

- ~1,1 MB de archivos de terceros en el repo, con origen auditable.
- Actualizar una librería es: descargar desde el `origen` del manifiesto a una carpeta de versión
  nueva, cambiar la ruta en `base.html` y el SHA-256 del manifiesto.
- `scripts/verificar_consola.py --offline` bloquea toda petición externa y es la prueba de que el
  dashboard funciona sin internet.
- Con `DEBUG=0`, los estáticos los sirve `collectstatic` + un servidor web: fuera de alcance del MVP.

## Relacionado
- `CLAUDE.md` §3 · OT-0008 · OT-0007 (riesgo de los CDN)
