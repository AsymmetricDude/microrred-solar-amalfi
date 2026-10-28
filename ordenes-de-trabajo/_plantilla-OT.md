---
id: OT-XXXX
tipo: feat            # feat | fix | refactor | chore | docs
titulo: "Título corto y accionable"
rama: ""              # <tipo>/ot-xxxx-slug
owner: ""             # quien la ejecuta
revisor: ""           # quien da el visto bueno y ordena el merge
depende_de: []        # OT previas
docs_ref: []          # CLAUDE.md, ADR, documento de investigación
creado: YYYY-MM-DD
---

# OT-XXXX — Título

> El estado NO se escribe aquí: vive en la columna «Estado» del índice (`00-README.md`).

## 1. Contexto y problema
Qué pasa hoy y por qué hay que hacerlo.

## 2. Objetivo
Una frase medible.

## 3. Alcance
**Qué SÍ entra:** …

**Qué NO entra:** …

**Alcance ampliado durante la ejecución:** _(vacío al crear la OT)_

## 4. Diseño / enfoque técnico
Archivos y por qué · modelo de datos · contrato de API · enfoque elegido frente a la alternativa.

## 5. Plan por fases
- [ ] **Fase 1 —** …

## 6. Criterios de aceptación (Definición de Done)
- [ ] Objetivo de §2 verificado en local (medido, no «debería funcionar»).
- [ ] `verify` en verde.
- [ ] Pruebas nuevas para la lógica crítica.
- [ ] Validador (subagente) sin bloqueantes; veredicto anotado en §9.

## 7. Checklist de cumplimiento
**Seguridad:** sin secretos en el diff; inputs validados; sin SQL crudo.
**Datos:** migraciones generadas por Django y aplicables desde cero.
**Calidad:** sin `print()` de depuración, sin magic numbers sueltos (constantes con nombre y unidad), una sola fuente de verdad por concepto.
**Reglas del producto (`CLAUDE.md`):** nombres de campos exactos; UI con Tailwind/Alpine/Chart.js por CDN; paleta semántica (esmeralda/ámbar/índigo/rojo).

## 8. Riesgos y rollback
- **Riesgo:** … → **Mitigación:** …
- **Rollback:** …

## 9. Bitácora
| Fecha | SHA | Nota |
|---|---|---|
| YYYY-MM-DD | | |
