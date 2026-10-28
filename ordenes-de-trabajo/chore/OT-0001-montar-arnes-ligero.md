---
id: OT-0001
tipo: chore
titulo: "Montar el arnés ligero de OT y definir el plan por fases"
rama: "main (commit inicial)"
owner: "claude-code"
revisor: "julian_murillo"
depende_de: []
docs_ref: [CLAUDE.md, "Downloads/deepseek_markdown_20261028_4863df.md", "Bóveda: Metodologia/Arnes_de_OT_con_Agentes, Metodologia/Plantilla_de_OT"]
creado: 2026-10-28
---

# OT-0001 — Montar el arnés ligero de OT y definir el plan por fases

## 1. Contexto y problema
El proyecto arranca vacío (sólo `CLAUDE.md`). El lead quiere trabajarlo **por partes**, con
la metodología de OT de su bóveda, y no empezar a construir hasta que cada parte tenga sus
fases definidas.

## 2. Objetivo
Existe un registro de planes en el repo (`ordenes-de-trabajo/` + `docs/adr/`) con **una OT
por cada punto del plan (1–6)**, cada una con diseño, fases y criterios de aceptación, y el
lead los aprueba antes de ejecutar la OT-0002.

## 3. Alcance
**Qué SÍ entra:** índice y plantilla adaptados al arnés ligero; ADR-0001 (datos sintéticos) y
ADR-0002 (uv + layout); OT-0002 a OT-0007 redactadas; `git init` con `.gitignore` y commit
inicial; sección de proceso en `CLAUDE.md`.

**Qué NO entra:** ningún código de la aplicación.

**Alcance ampliado durante la ejecución:** _(vacío)_

## 4. Diseño / enfoque técnico
- Del arnés completo se conserva: OT con las 9 secciones, regla de raíz, tipo = rama = commit,
  diseño antes que código, validador distinto del autor, bitácora con evidencia medida.
- Se quita: repo hub separado, Issues, board, PR remotos (decisión del lead, 2026-10-28).
  El estado vive en la columna «Estado» del índice.
- Mapeo plan del lead → OT:

  | Punto del plan | OT |
  |---|---|
  | 0. Metodología | OT-0001 |
  | 1. Inicialización y estructura | OT-0002 |
  | 2. Modelos y migraciones | OT-0003 |
  | 3. Generador sintético | OT-0004 |
  | 4. Backend y endpoints JSON | OT-0005 |
  | 5. Frontend (6 módulos) | OT-0006 |
  | 6. Verificación | Cada OT verifica lo suyo (§6) + OT-0007 integral |

## 5. Plan por fases
- [x] **Fase 1 —** Leer `CLAUDE.md`, el documento de investigación y la metodología de la bóveda.
- [x] **Fase 2 —** Decisiones del lead: arnés ligero con git local; entorno con `uv`.
- [x] **Fase 3 —** Índice, plantilla, ADR-0001, ADR-0002, OT-0002…OT-0007.
- [x] **Fase 4 —** `git init`, `.gitignore`, commit inicial.
- [x] **Fase 5 —** El lead revisa las OT y responde las preguntas abiertas (§8 de cada OT).

## 6. Criterios de aceptación
- [x] Cada punto 1–6 del plan tiene su OT con §4 (diseño) y §5 (fases) completos.
- [x] El lead aprueba el plan (o pide cambios) antes de iniciar OT-0002.

## 7. Checklist de cumplimiento
Sin secretos; documentación en español, coherente con `CLAUDE.md`.

## 8. Riesgos y rollback
- **Riesgo:** el documento de investigación contradice `CLAUDE.md` (CSV/joblib). →
  **Mitigación:** ADR-0001 deja escrito que manda `CLAUDE.md` para el MVP.

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| 2026-10-28 | — | Leída la bóveda: `Arnes_de_OT_con_Agentes`, `Plantilla_de_OT`, `00_Kit_de_Arranque_de_Proyecto`, `Artefacto_Documentos_del_Hub_de_OT`, `Trabajar_con_Agentes_de_Codigo`, `Framework_Evidencia_Medida_vs_Afirmada`; y la estructura real de `~/cuentas-claras/cuentas-claras-ot`. |
| 2026-10-28 | — | Lead decide: arnés ligero + git local (sin GitHub por ahora) y `uv`. Medido: Python 3.12.3, uv 0.11.32. |
| 2026-10-28 | d9de193 | Commit inicial del arnés y del plan. |
| 2026-10-28 | — | Lead aprueba el plan y resuelve las 4 preguntas: tasa 12 % E.A. (con LCOE comparado contra el diésel nivelado, ver OT-0004 §9); diésel 3 000 COP/kWh y 0,8 kgCO₂/kWh como constantes en la cabecera del seeder; FK/O2O `registro`; aviso de Tailwind CDN aceptado. |
