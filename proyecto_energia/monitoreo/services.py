"""Armado del JSON del dashboard (OT-0005). La vista sólo valida la petición y lo serializa.

Cinco consultas como máximo, sea cual sea el rango: último timestamp, registros con su
analítica, segmentos, resumen financiero y flujo de caja.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from django.db.models import Max
from django.utils import timezone

from analitica import services as analitica
from financiero import calculos
from financiero.models import FlujoCajaAnual, ResumenFinanciero
from monitoreo.management.commands import seed_amalfi_data as supuestos
from monitoreo.models import ConsumoPorSegmento, RegistroSistema

DIAS_PERMITIDOS = (1, 7, 30)
DIAS_POR_DEFECTO = 7
DECIMALES = 2
# Sólo dígitos ASCII: str.isdigit() acepta «²» y otros dígitos Unicode que int() rechaza.
PATRON_DIAS = re.compile(r"[0-9]{1,3}")
# Formato estricto: date.fromisoformat también acepta «20261010» o «2026-W41-1».
PATRON_FECHA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
CLAVES_SERIES = (
    "timestamps",
    "generacion",
    "demanda",
    "irradiancia",
    "temp_ambiente",
    "temp_panel",
    "soc",
    "potencia_bateria",
    "autonomia",
    "generacion_predicha",
    "demanda_predicha",
)
TIPOS_ANOMALIA_GENERACION = (
    analitica.FALLA_INVERSOR,
    analitica.SOMBREADO_PARCIAL,
    analitica.GENERACION_ATIPICA,
)


class ParametrosInvalidos(ValueError):
    """La petición no describe un rango válido; la vista responde 400 con el mensaje."""


@dataclass(frozen=True)
class Rango:
    desde: datetime | None  # inclusivo; None si la base está vacía
    hasta: datetime | None  # inclusivo
    dias: int | None  # None cuando se pidió por fechas


def _fecha(texto: str, nombre: str) -> date:
    mensaje = f"'{nombre}' debe ser una fecha válida con formato AAAA-MM-DD."
    if not PATRON_FECHA.fullmatch(texto):
        raise ParametrosInvalidos(mensaje)
    try:
        return date.fromisoformat(texto)
    except ValueError as error:
        raise ParametrosInvalidos(mensaje) from error


def _momento_local(dia: date, hora: time) -> datetime:
    """Fecha y hora de Bogotá, comprobando que también exista en UTC (la base guarda UTC):
    9999-12-31 23:59 −05:00 es el año 10 000 en UTC y desbordaría al consultar."""
    momento = datetime.combine(dia, hora, tzinfo=timezone.get_current_timezone())
    try:
        momento.astimezone(UTC)
    except OverflowError as error:
        raise ParametrosInvalidos("Fecha fuera del rango admitido.") from error
    return momento


def resolver_rango(parametros) -> Rango:
    """`desde`/`hasta` (fechas locales, inclusivas) tienen prioridad sobre `dias`.

    `dias=N` son las N·24 horas que terminan en el **último registro** de la base, no en la
    hora actual: una base sembrada hace días no devuelve «últimas 24 h» vacías.
    """
    desde_txt, hasta_txt = parametros.get("desde"), parametros.get("hasta")
    if desde_txt or hasta_txt:
        if not (desde_txt and hasta_txt):
            raise ParametrosInvalidos("Envía 'desde' y 'hasta' juntos.")
        desde, hasta = _fecha(desde_txt, "desde"), _fecha(hasta_txt, "hasta")
        if desde > hasta:
            raise ParametrosInvalidos("'desde' no puede ser posterior a 'hasta'.")
        # Fin del día con time.max: no supone que los registros caigan en punto.
        return Rango(_momento_local(desde, time.min), _momento_local(hasta, time.max), None)

    dias_txt = parametros.get("dias", str(DIAS_POR_DEFECTO))
    if not PATRON_DIAS.fullmatch(dias_txt) or int(dias_txt) not in DIAS_PERMITIDOS:
        permitidos = ", ".join(map(str, DIAS_PERMITIDOS))
        raise ParametrosInvalidos(f"'dias' debe ser uno de: {permitidos}.")
    dias = int(dias_txt)
    ultimo = RegistroSistema.objects.aggregate(ultimo=Max("timestamp"))["ultimo"]
    if ultimo is None:
        return Rango(None, None, dias)
    return Rango(ultimo - timedelta(hours=dias * 24 - 1), ultimo, dias)


def _r(valor: float | None, decimales: int = DECIMALES) -> float | None:
    return None if valor is None else round(valor, decimales)


def _iso(momento: datetime) -> str:
    return timezone.localtime(momento).isoformat()


def balance_residual(registro: RegistroSistema) -> float:
    """generación − demanda − potencia de batería.

    Del balance horario de la simulación (OT-0004 §4.6): positivo es vertimiento, negativo es
    energía no suministrada. En una misma hora sólo uno de los dos puede ser distinto de cero.
    """
    return registro.generacion_fv_kwh - registro.demanda_total_kwh - registro.potencia_bateria_kw


def _metricas(pares: list[tuple[float, float]]) -> dict:
    """MAE, RMSE y R² de pares (real, predicho)."""
    if not pares:
        return {"mae": None, "rmse": None, "r2": None, "n": 0}
    reales = [real for real, _ in pares]
    predichos = [predicho for _, predicho in pares]
    return {
        "mae": _r(analitica.mae(reales, predichos), 3),
        "rmse": _r(analitica.rmse(reales, predichos), 3),
        "r2": _r(analitica.r2(reales, predichos), 4),
        "n": len(pares),
    }


def _payload_vacio(rango: Rango) -> dict:
    return {
        "rango": {"desde": None, "hasta": None, "dias": rango.dias, "n_registros": 0},
        "sin_datos": True,
        "kpis": None,
        "estados": {e: 0 for e in RegistroSistema.EstadoSistema.values},
        # Misma forma que con datos: la UI no tiene que distinguir claves ausentes.
        "series": {clave: [] for clave in CLAVES_SERIES},
        "segmentos": None,
        "analitica": None,
    }


def construir_payload(rango: Rango) -> dict:
    registros = []
    if rango.desde is not None:
        registros = list(
            RegistroSistema.objects.filter(timestamp__gte=rango.desde, timestamp__lte=rango.hasta)
            .select_related("analitica")
            .order_by("timestamp")
        )
    payload = _payload_vacio(rango) if not registros else _payload_series(rango, registros)
    payload["umbrales_soc"] = {
        "minimo": supuestos.SOC_MINIMO_PCT,
        "alerta": supuestos.UMBRAL_ALERTA_PCT,
        "optimo": supuestos.UMBRAL_OPTIMO_PCT,
    }
    payload["financiero"] = _financiero()
    return payload


def _payload_series(rango: Rango, registros: list[RegistroSistema]) -> dict:
    indice = {r.id: i for i, r in enumerate(registros)}
    n = len(registros)

    # Segmentos: una consulta para todo el rango, ubicados por la posición de su registro.
    segmentos = {tipo: [0.0] * n for tipo in ConsumoPorSegmento.TipoUsuario.values}
    for registro_id, tipo, consumo in ConsumoPorSegmento.objects.filter(
        registro__timestamp__gte=registros[0].timestamp,
        registro__timestamp__lte=registros[-1].timestamp,
    ).values_list("registro_id", "tipo_usuario", "consumo_kwh"):
        segmentos[tipo][indice[registro_id]] = consumo
    totales_segmento = {tipo: sum(valores) for tipo, valores in segmentos.items()}

    residuos = [balance_residual(r) for r in registros]
    vertimiento = sum(x for x in residuos if x > 0)
    no_suministrada = sum(-x for x in residuos if x < 0)
    generacion = sum(r.generacion_fv_kwh for r in registros)
    demanda = sum(r.demanda_total_kwh for r in registros)
    servida = demanda - no_suministrada
    pico = max(registros, key=lambda r: r.demanda_total_kwh)
    actual = registros[-1]

    predicciones = [getattr(r, "analitica", None) for r in registros]
    gen_pred = [p.generacion_predicha_kwh if p else None for p in predicciones]
    dem_pred = [p.demanda_predicha_kwh if p else None for p in predicciones]
    # Generación: sólo horas con sol (real o predicha > 0). Las noches, 0 contra 0, inflarían
    # el R² sin decir nada del modelo. Demanda: todas las horas.
    pares_gen = [
        (r.generacion_fv_kwh, p)
        for r, p in zip(registros, gen_pred, strict=True)
        if p is not None and (r.generacion_fv_kwh > 0 or p > 0)
    ]
    pares_dem = [
        (r.demanda_total_kwh, p) for r, p in zip(registros, dem_pred, strict=True) if p is not None
    ]

    anomalias = []
    for r, p in zip(registros, predicciones, strict=True):
        if p is None or not p.es_anomalia:
            continue
        es_generacion = p.tipo_anomalia in TIPOS_ANOMALIA_GENERACION
        real = r.generacion_fv_kwh if es_generacion else r.demanda_total_kwh
        predicho = p.generacion_predicha_kwh if es_generacion else p.demanda_predicha_kwh
        anomalias.append(
            {
                "timestamp": _iso(r.timestamp),
                "tipo": p.tipo_anomalia,
                "variable": "generacion" if es_generacion else "demanda",
                "descripcion": p.descripcion_anomalia,
                "real_kwh": _r(real),
                "predicho_kwh": _r(predicho),
                "desviacion_pct": _r((real / predicho - 1) * 100, 1) if predicho else None,
            }
        )

    return {
        "rango": {
            "desde": _iso(registros[0].timestamp),
            "hasta": _iso(actual.timestamp),
            "dias": rango.dias,
            "n_registros": n,
        },
        "sin_datos": False,
        "kpis": {
            "generacion_kwh": _r(generacion),
            "demanda_kwh": _r(demanda),
            "energia_servida_kwh": _r(servida),
            "vertimiento_kwh": _r(vertimiento),
            "energia_no_suministrada_kwh": _r(no_suministrada),
            "soc_actual": _r(actual.soc_porcentaje, 1),
            "autonomia_horas": _r(actual.autonomia_horas, 1),
            "estado_actual": actual.estado_sistema,
            "potencia_bateria_actual_kw": _r(actual.potencia_bateria_kw),
            # Ahorro y CO₂ del rango: energía servida × supuestos del seeder (única fuente).
            "ahorro_cop": round(servida * supuestos.COSTO_DIESEL_EVITADO_COP_KWH),
            "co2_evitado_t": _r(servida * supuestos.FACTOR_EMISION_KGCO2_KWH / 1000, 3),
            "demanda_pico_kwh": _r(pico.demanda_total_kwh),
            "demanda_pico_ts": _iso(pico.timestamp),
        },
        "estados": {
            e: sum(r.estado_sistema == e for r in registros)
            for e in RegistroSistema.EstadoSistema.values
        },
        "series": {
            "timestamps": [_iso(r.timestamp) for r in registros],
            "generacion": [_r(r.generacion_fv_kwh) for r in registros],
            "demanda": [_r(r.demanda_total_kwh) for r in registros],
            "irradiancia": [_r(r.irradiancia_wm2, 1) for r in registros],
            "temp_ambiente": [_r(r.temp_ambiente_c, 1) for r in registros],
            "temp_panel": [_r(r.temp_panel_c, 1) for r in registros],
            "soc": [_r(r.soc_porcentaje, 1) for r in registros],
            "potencia_bateria": [_r(r.potencia_bateria_kw) for r in registros],
            "autonomia": [_r(r.autonomia_horas, 1) for r in registros],
            "generacion_predicha": [_r(p) for p in gen_pred],
            "demanda_predicha": [_r(p) for p in dem_pred],
        },
        "segmentos": {
            "series": {tipo: [_r(v) for v in valores] for tipo, valores in segmentos.items()},
            "totales_kwh": {tipo: _r(total) for tipo, total in totales_segmento.items()},
            "participacion_pct": {
                tipo: _r(total / demanda * 100 if demanda else 0, 1)
                for tipo, total in totales_segmento.items()
            },
        },
        "analitica": {
            "metricas": {
                "generacion": _metricas(pares_gen),
                "demanda": _metricas(pares_dem),
            },
            "anomalias": anomalias,
        },
    }


def _financiero() -> dict | None:
    resumen = ResumenFinanciero.actual()
    if resumen is None:
        return None
    filas = [
        calculos.FilaFlujo(
            f.anio,
            f.ingresos_ahorro_cop,
            f.costos_om_cop,
            f.flujo_neto_cop,
            f.flujo_acumulado_cop,
        )
        for f in FlujoCajaAnual.objects.order_by("anio")
    ]
    return {
        "resumen": {
            "capex_cop": resumen.capex_cop,
            "opex_anual_cop": resumen.opex_anual_cop,
            "vpn_cop": resumen.vpn_cop,
            "tir_porcentaje": resumen.tir_porcentaje,
            "lcoe_cop_kwh": resumen.lcoe_cop_kwh,
            "ahorro_anual_diesel_cop": resumen.ahorro_anual_diesel_cop,
            "toneladas_co2_evitadas_anual": resumen.toneladas_co2_evitadas_anual,
        },
        "tasa_descuento_pct": _r(supuestos.TASA_DESCUENTO * 100, 1),
        "costo_nivelado_diesel_cop_kwh": _r(calculos.costo_nivelado_diesel(supuestos.FINANZAS)),
        "anio_reemplazo_baterias": supuestos.ANIO_REEMPLAZO_BATERIAS,
        "payback_simple_anios": _r(calculos.payback_anios(filas)),
        "flujo": [
            {
                "anio": f.anio,
                "ingresos_ahorro_cop": f.ingresos_ahorro_cop,
                "costos_om_cop": f.costos_om_cop,
                "flujo_neto_cop": f.flujo_neto_cop,
                "flujo_acumulado_cop": f.flujo_acumulado_cop,
            }
            for f in filas
        ],
    }
