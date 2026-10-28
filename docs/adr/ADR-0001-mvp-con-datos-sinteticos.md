---
id: ADR-0001
titulo: "El MVP se alimenta de un generador sintético, no del CSV ni de modelos .joblib"
estado: aceptada
fecha: 2026-10-28
supersede: ""
tags: [adr, decision, datos, alcance]
---

# ADR-0001 — El MVP se alimenta de un generador sintético, no del CSV ni de modelos .joblib

## Contexto

- El documento de investigación (`deepseek_markdown_20261028_4863df.md`, arquitectura del
  trabajo de grado) describe un flujo **CSV → `cargar_datos.py` → ORM** y una capa de IA con
  Scikit-Learn y modelos `.joblib` en `analitica/modelos/`.
- `CLAUDE.md` §2 acota el MVP: **sin ingesta de CSV externo ni entrenamiento `.joblib`**; todo
  sale de `python manage.py seed_amalfi_data`.
- No hay todavía datos de sensores reales de Amalfi.

## Decisión

- La única fuente de datos del MVP es el management command `seed_amalfi_data`
  (OT-0004), con semilla aleatoria fija para que sea **reproducible**.
- Las «predicciones ML» son **mock**: valor físico esperado + error aleatorio acotado. Se
  guardan en `PrediccionYAnomalia` con el mismo esquema que usaría un modelo real.
- Las métricas de error (MAE, RMSE, R²) **se calculan** sobre real vs. predicho; no se
  escriben a mano.
- El módulo financiero muestra indicadores **calculados a partir del flujo de caja
  sembrado** (VPN, TIR y LCOE salen del flujo, no se teclean), sin recálculo interactivo.

## Consecuencias

- El esquema (5 modelos) es el definitivo: cuando lleguen el CSV y el modelo entrenado, sólo
  se añade un comando de ingesta y un servicio de predicción; vistas y frontend no cambian.
- Toda cifra mostrada es **sintética**. El dashboard debe decirlo de forma visible
  («Datos sintéticos — caso de estudio») para que no se lea como medición real.

## Relacionado
- `CLAUDE.md` §2 · OT-0004 · OT-0005
