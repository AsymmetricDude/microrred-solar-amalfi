"""Siembra datos sintéticos físicamente coherentes de la microrred de Amalfi (ADR-0001).

    uv run python manage.py seed_amalfi_data [--dias 30] [--semilla 42]

Borra los datos previos y genera, en una sola transacción, las horas de los últimos N días
(hasta la última hora completa), sus segmentos de demanda, predicciones y anomalías, el
resumen financiero y el flujo de caja de 25 años.

╔════════════════════════════════════════════════════════════════════════════════════════╗
║  SUPUESTOS DEL CASO DE ESTUDIO — única fuente de verdad                                  ║
║  Si la autora actualiza un supuesto en el documento escrito, se cambia aquí y se vuelve  ║
║  a ejecutar el comando. La API y el dashboard leen estos mismos valores.                ║
║  Las pruebas avisan si un cambio saca la TIR del rango [14 %, 15 %] o el LCOE deja de    ║
║  ser competitivo frente al diésel.                                                       ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analitica.models import PrediccionYAnomalia
from financiero import calculos
from financiero.models import FlujoCajaAnual, ResumenFinanciero
from monitoreo import simulacion
from monitoreo.models import ConsumoPorSegmento, RegistroSistema

# ── Supuestos financieros (COP) ─────────────────────────────────────────────────────────────
# Tasa social de descuento de referencia del DNP para proyectos en ZNI (decisión del lead).
TASA_DESCUENTO = 0.12  # 12 % efectivo anual
HORIZONTE_ANIOS = 25
# Inversión: 50 kWp FV + banco de 120 kWh + red de distribución + logística de ZNI.
# Calibrado para que la TIR quede en ≈ 14,5 % (aritmética en la bitácora de OT-0004).
CAPEX_COP = 1_150_000_000
OPEX_FRACCION_CAPEX = 0.015  # O&M anual = 1,5 % del CAPEX en el año 1
INFLACION_OPEX = 0.03  # crecimiento anual REAL del O&M (sobre la inflación; logística ZNI)
REEMPLAZO_BATERIAS_COP = 130_000_000
ANIO_REEMPLAZO_BATERIAS = 10
# Costo evitado de generar con diésel en la ZNI (combustible + transporte + O&M del grupo).
COSTO_DIESEL_EVITADO_COP_KWH = 3_000  # año 1; aprobado por el lead
# Escalamientos en términos REALES, coherentes con la TSD (tasa real); decisión del lead.
ESCALAMIENTO_DIESEL = 0.03  # crecimiento anual real del costo del diésel en ZNI
# Energía servida en el año 1; se contrasta con el mes simulado (prueba de ±15 %).
ENERGIA_ANUAL_SERVIDA_KWH = 56_500
# 0,5 %/año, típico de fabricante. Se aplica a la energía servida aunque hoy se vierte ~24 % de
# la generación: es conservador (la degradación real recortaría primero el vertimiento).
DEGRADACION_FV_ANUAL = 0.005

# ── Supuesto ambiental ──────────────────────────────────────────────────────────────────────
# 2,68 kgCO₂ por litro de ACPM × 0,30 L/kWh de un grupo electrógeno pequeño.
FACTOR_EMISION_KGCO2_KWH = 0.80  # aprobado por el lead

# ── Planta fotovoltaica ─────────────────────────────────────────────────────────────────────
POTENCIA_PICO_KWP = 50.0
COEF_TEMPERATURA_POTENCIA = -0.0040  # pérdida de potencia por °C sobre 25 °C (silicio)
EFICIENCIA_BOS = 0.86  # inversor, cableado y suciedad
COEF_CALENTAMIENTO_PANEL = 0.019  # °C por W/m²: 1 000 W/m² con 29 °C → ≈ 48 °C

# ── Banco de baterías ───────────────────────────────────────────────────────────────────────
CAPACIDAD_BATERIA_KWH = 120.0
SOC_INICIAL_PCT = 70.0
SOC_MINIMO_PCT = 15.0  # reserva que protege la vida útil
SOC_MAXIMO_PCT = 100.0
EFICIENCIA_CARGA = 0.95
EFICIENCIA_DESCARGA = 0.95
POTENCIA_MAX_BATERIA_KW = 50.0
UMBRAL_OPTIMO_PCT = 40.0  # SoC ≥ 40 % → OPTIMO
UMBRAL_ALERTA_PCT = 25.0  # 25 % ≤ SoC < 40 % → ALERTA; < 25 % → CRITICO

# ── Ventana de datos ────────────────────────────────────────────────────────────────────────
DIAS_POR_DEFECTO = 30
DIAS_MINIMOS = 14  # menos días no dejan fechas suficientes para 6–8 anomalías y el frente
SEMILLA_POR_DEFECTO = 42

PLANTA = simulacion.ParametrosPlanta(
    potencia_pico_kwp=POTENCIA_PICO_KWP,
    coef_temperatura_potencia=COEF_TEMPERATURA_POTENCIA,
    eficiencia_bos=EFICIENCIA_BOS,
    coef_calentamiento_panel=COEF_CALENTAMIENTO_PANEL,
    capacidad_bateria_kwh=CAPACIDAD_BATERIA_KWH,
    soc_inicial_pct=SOC_INICIAL_PCT,
    soc_minimo_pct=SOC_MINIMO_PCT,
    soc_maximo_pct=SOC_MAXIMO_PCT,
    eficiencia_carga=EFICIENCIA_CARGA,
    eficiencia_descarga=EFICIENCIA_DESCARGA,
    potencia_max_bateria_kw=POTENCIA_MAX_BATERIA_KW,
    umbral_optimo_pct=UMBRAL_OPTIMO_PCT,
    umbral_alerta_pct=UMBRAL_ALERTA_PCT,
)

FINANZAS = calculos.ParametrosFinancieros(
    capex_cop=CAPEX_COP,
    opex_fraccion_capex=OPEX_FRACCION_CAPEX,
    reemplazo_baterias_cop=REEMPLAZO_BATERIAS_COP,
    anio_reemplazo_baterias=ANIO_REEMPLAZO_BATERIAS,
    costo_diesel_evitado_cop_kwh=COSTO_DIESEL_EVITADO_COP_KWH,
    escalamiento_diesel=ESCALAMIENTO_DIESEL,
    inflacion_opex=INFLACION_OPEX,
    degradacion_fv_anual=DEGRADACION_FV_ANUAL,
    energia_anual_servida_kwh=ENERGIA_ANUAL_SERVIDA_KWH,
    tasa_descuento=TASA_DESCUENTO,
    horizonte_anios=HORIZONTE_ANIOS,
    factor_emision_kgco2_kwh=FACTOR_EMISION_KGCO2_KWH,
)

# Filas por INSERT en bulk_create: acota el tamaño de cada sentencia sin perder velocidad.
TAMANO_LOTE = 1000


def inicio_de_ventana(dias: int):
    """Primera hora de la ventana que termina en la última hora completa (hora local)."""
    ahora = timezone.localtime()
    ultima_completa = ahora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    return ultima_completa - timedelta(hours=dias * 24 - 1)


class Command(BaseCommand):
    help = "Borra y regenera los datos sintéticos de la microrred de Amalfi (últimos N días)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=DIAS_POR_DEFECTO)
        parser.add_argument("--semilla", type=int, default=SEMILLA_POR_DEFECTO)

    def handle(self, *args, dias, semilla, **options):
        if dias < DIAS_MINIMOS:
            raise CommandError(f"--dias debe ser al menos {DIAS_MINIMOS}.")
        try:
            escenario = simulacion.generar_escenario(
                inicio_de_ventana(dias), dias * 24, semilla, PLANTA
            )
        except ValueError as error:
            raise CommandError(f"{error} (semilla {semilla}).") from error
        filas = calculos.flujo_de_caja(FINANZAS)
        kpis = calculos.indicadores(FINANZAS, filas)
        with transaction.atomic():
            self._borrar_datos_previos()
            self._guardar_series(escenario)
            self._guardar_financiero(filas, kpis)
        self._reportar(escenario, kpis)

    def _borrar_datos_previos(self):
        # Segmentos y predicciones caen en cascada con sus registros.
        RegistroSistema.objects.all().delete()
        ResumenFinanciero.objects.all().delete()
        FlujoCajaAnual.objects.all().delete()

    def _guardar_series(self, escenario):
        registros = RegistroSistema.objects.bulk_create(
            [
                RegistroSistema(
                    timestamp=h.timestamp,
                    irradiancia_wm2=h.irradiancia_wm2,
                    temp_ambiente_c=h.temp_ambiente_c,
                    temp_panel_c=h.temp_panel_c,
                    generacion_fv_kwh=h.generacion_fv_kwh,
                    demanda_total_kwh=h.demanda_total_kwh,
                    soc_porcentaje=h.soc_porcentaje,
                    autonomia_horas=h.autonomia_horas,
                    potencia_bateria_kw=h.potencia_bateria_kw,
                    estado_sistema=h.estado_sistema,
                )
                for h in escenario.horas
            ],
            batch_size=TAMANO_LOTE,
        )
        ConsumoPorSegmento.objects.bulk_create(
            [
                ConsumoPorSegmento(registro=r, tipo_usuario=tipo, consumo_kwh=consumo)
                for r, h in zip(registros, escenario.horas, strict=True)
                for tipo, consumo in h.segmentos.items()
            ],
            batch_size=TAMANO_LOTE,
        )
        PrediccionYAnomalia.objects.bulk_create(
            [
                PrediccionYAnomalia(
                    registro=r,
                    generacion_predicha_kwh=h.generacion_predicha_kwh,
                    demanda_predicha_kwh=h.demanda_predicha_kwh,
                    es_anomalia=h.deteccion is not None,
                    tipo_anomalia=h.deteccion.tipo if h.deteccion else None,
                    descripcion_anomalia=h.deteccion.descripcion if h.deteccion else None,
                )
                for r, h in zip(registros, escenario.horas, strict=True)
            ],
            batch_size=TAMANO_LOTE,
        )

    def _guardar_financiero(self, filas, kpis):
        ResumenFinanciero.objects.create(
            capex_cop=FINANZAS.capex_cop,
            opex_anual_cop=FINANZAS.opex_anual_cop,
            vpn_cop=kpis.vpn_cop,
            tir_porcentaje=kpis.tir_porcentaje,
            lcoe_cop_kwh=kpis.lcoe_cop_kwh,
            ahorro_anual_diesel_cop=kpis.ahorro_anual_diesel_cop,
            toneladas_co2_evitadas_anual=kpis.toneladas_co2_evitadas_anual,
        )
        FlujoCajaAnual.objects.bulk_create(
            [
                FlujoCajaAnual(
                    anio=f.anio,
                    ingresos_ahorro_cop=f.ingresos_ahorro_cop,
                    costos_om_cop=f.costos_om_cop,
                    flujo_neto_cop=f.flujo_neto_cop,
                    flujo_acumulado_cop=f.flujo_acumulado_cop,
                )
                for f in filas
            ]
        )

    def _reportar(self, escenario, kpis):
        horas = escenario.horas
        generacion = sum(h.generacion_fv_kwh for h in horas)
        demanda = sum(h.demanda_total_kwh for h in horas)
        no_suministrada = sum(h.energia_no_suministrada_kwh for h in horas)
        vertida = sum(h.vertimiento_kwh for h in horas)
        estados = {
            e: sum(h.estado_sistema == e for h in horas)
            for e in (simulacion.ESTADO_OPTIMO, simulacion.ESTADO_ALERTA, simulacion.ESTADO_CRITICO)
        }
        detectadas = sum(h.deteccion is not None for h in horas)
        primera, ultima = (timezone.localtime(horas[i].timestamp) for i in (0, -1))
        lineas = [
            f"Ventana: {primera:%Y-%m-%d %H:%M} → {ultima:%Y-%m-%d %H:%M} ({len(horas)} h)",
            f"Generación FV: {generacion:,.0f} kWh · Demanda: {demanda:,.0f} kWh",
            f"Vertimiento: {vertida:,.0f} kWh · No suministrada: {no_suministrada:,.0f} kWh",
            f"Estados: {estados}",
            f"Frente lluvioso: {', '.join(f.isoformat() for f in escenario.fechas_frente)}",
            f"Anomalías inyectadas: {len(escenario.anomalias)} · detectadas: {detectadas}",
            f"TIR {kpis.tir_porcentaje:.2f} % · VPN {kpis.vpn_cop:,} COP · "
            f"LCOE {kpis.lcoe_cop_kwh:,.0f} vs. diésel nivelado "
            f"{kpis.costo_nivelado_diesel_cop_kwh:,.0f} COP/kWh · "
            f"payback {kpis.payback_anios:.1f} años",
        ]
        for linea in lineas:
            self.stdout.write(linea)
        self.stdout.write(self.style.SUCCESS("Datos de Amalfi sembrados."))
