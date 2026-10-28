# Contexto del Proyecto: Modelo de Gestión Inteligente - Comunidad Energética Rural (Amalfi, Antioquia)

## 1. Descripción General
Aplicación web monolítica en Django para el monitoreo, gestión de demanda, almacenamiento, analítica predictiva (mock) y evaluación financiera de una microrred solar fotovoltaica en una Zona No Interconectada (ZNI) en Amalfi, Antioquia[cite: 1].

## 2. Alcance de la Fase Actual (MVP)
- **SIN ingesta de CSV externo ni entrenamiento de modelos `.joblib` en tiempo real.**
- Toda la aplicación se alimentará mediante un **generador de datos sintéticos físicamente coherentes** (`python manage.py seed_amalfi_data`).
- El módulo financiero mostrará indicadores estáticos del caso de estudio y el flujo de caja proyectado a 25 años desde la base de datos (sin recálculo interactivo en vivo)[cite: 1].

## 3. Stack Tecnológico y Reglas de UI/UX
- **Backend:** Python 3.11+ y Django 5.x[cite: 1].
- **Base de Datos:** SQLite para desarrollo local (preparado en ORM para migrar a PostgreSQL)[cite: 1].
- **Frontend:** Django Templates + **TailwindCSS** + **Alpine.js** para interactividad ligera de pestañas/filtros + **Chart.js** para visualización de datos[cite: 1] + **Lucide Icons** (o Heroicons). Todas **servidas localmente** desde `monitoreo/static/vendor/` (versión, origen y SHA-256 en su `MANIFIESTO.json`), sin CDN ni paso de compilación, para operar sin internet en la ZNI ([ADR-0003](docs/adr/ADR-0003-frontend-sin-internet.md)).
- **Estilo Visual:** Diseño moderno tipo SaaS energético (estilo Clean/Dark-Sidebar o Slate/Emerald palette). Tarjetas con bordes sutiles (`border-slate-200`), sombras suaves (`shadow-sm`), tipografía `Inter` y colores semánticos claros (Esmeralda para generación/óptimo, Ámbar para alerta/irradiancia, Índigo/Azul para demanda, Rojo para crítico/anomalías).

## 4. Estructura del Proyecto y Esquema de Base de Datos (4 Bloques)
El proyecto `proyecto_energia` tendrá 3 aplicaciones modulares[cite: 1]:

### A. App `monitoreo` (Core y Vista Principal del Dashboard)[cite: 1]
1. **`RegistroSistema`**: Serie temporal horaria (indexada por `timestamp`).
   - `timestamp` (DateTimeField, unique=True, db_index=True)
   - `irradiancia_wm2` (FloatField)[cite: 1]
   - `temp_ambiente_c` (FloatField)
   - `temp_panel_c` (FloatField)[cite: 1]
   - `generacion_fv_kwh` (FloatField)[cite: 1]
   - `demanda_total_kwh` (FloatField)
   - `soc_porcentaje` (FloatField - 0 a 100%)[cite: 1]
   - `autonomia_horas` (FloatField)[cite: 1]
   - `potencia_bateria_kw` (FloatField - positivo carga, negativo descarga)
   - `estado_sistema` (CharField: `'OPTIMO'`, `'ALERTA'`, `'CRITICO'`)[cite: 1]
2. **`ConsumoPorSegmento`**: Desglose horario de demanda (`ForeignKey` a `RegistroSistema`, `related_name='segmentos'`).
   - `tipo_usuario` (CharField choices: `'RESIDENCIAL'`, `'PRODUCTIVO'`, `'COMUNITARIO'`, `'ALUMBRADO'`)[cite: 1]
   - `consumo_kwh` (FloatField)[cite: 1]

### B. App `analitica` (Predicciones Mock y Anomalías)[cite: 1]
3. **`PrediccionYAnomalia`**: Relación `OneToOneField` con `RegistroSistema` (`related_name='analitica'`).
   - `generacion_predicha_kwh` (FloatField)[cite: 1]
   - `demanda_predicha_kwh` (FloatField)[cite: 1]
   - `es_anomalia` (BooleanField, default=False)[cite: 1]
   - `tipo_anomalia` (CharField, blank=True, null=True)
   - `descripcion_anomalia` (TextField, blank=True, null=True)

### C. App `financiero` (Evaluación Económica del Caso de Estudio)[cite: 1]
4. **`ResumenFinanciero`**: Registro único con KPIs del proyecto.
   - `capex_cop` (BigIntegerField)
   - `opex_anual_cop` (BigIntegerField)
   - `vpn_cop` (BigIntegerField)[cite: 1]
   - `tir_porcentaje` (FloatField)[cite: 1]
   - `lcoe_cop_kwh` (FloatField)[cite: 1]
   - `ahorro_anual_diesel_cop` (BigIntegerField)
   - `toneladas_co2_evitadas_anual` (FloatField)
5. **`FlujoCajaAnual`**: Serie de tiempo de 0 a 25 años[cite: 1].
   - `anio` (IntegerField, unique=True)
   - `ingresos_ahorro_cop` (BigIntegerField)
   - `costos_om_cop` (BigIntegerField)
   - `flujo_neto_cop` (BigIntegerField)
   - `flujo_acumulado_cop` (BigIntegerField)

## 5. Proceso de Trabajo (Arnés Ligero de OT)
- Todo trabajo se registra como **Orden de Trabajo** en [`ordenes-de-trabajo/`](ordenes-de-trabajo/00-README.md); las decisiones de arquitectura, en [`docs/adr/`](docs/adr/).
- **Se diseña antes de codear** y **se trabaja por partes**: ninguna OT pasa a «En curso» sin que el lead apruebe su §4-§5; al terminar cada OT se para y se reporta.
- Git local, una rama por OT (`<tipo>/ot-####-slug`), commit con `Implements OT-####`. Entorno con `uv` (`uv run ...`).
- Antes de pedir revisión: comando `verify` del índice en verde + validador (subagente distinto del autor).
