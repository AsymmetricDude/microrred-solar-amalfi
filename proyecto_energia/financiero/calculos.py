"""Evaluación económica de la microrred (lógica pura, sin ORM).

Los valores de los parámetros viven en la cabecera de
`monitoreo/management/commands/seed_amalfi_data.py` (decisión del lead, OT-0004 §4.8).
Aquí sólo están las fórmulas: VPN, TIR y LCOE se calculan del flujo, nunca se teclean.
"""

from dataclasses import dataclass

# Tolerancia y tope de iteraciones de la bisección de la TIR.
TIR_TOLERANCIA = 1e-9
TIR_MAX_ITERACIONES = 200


@dataclass(frozen=True)
class ParametrosFinancieros:
    capex_cop: int
    opex_fraccion_capex: float  # OPEX del año 1 como fracción del CAPEX
    reemplazo_baterias_cop: int
    anio_reemplazo_baterias: int
    costo_diesel_evitado_cop_kwh: float  # costo del diésel evitado en el año 1
    escalamiento_diesel: float  # crecimiento anual del costo del diésel
    inflacion_opex: float
    degradacion_fv_anual: float
    energia_anual_servida_kwh: float  # energía del año 1
    tasa_descuento: float
    horizonte_anios: int
    factor_emision_kgco2_kwh: float

    @property
    def opex_anual_cop(self) -> int:
        return round(self.capex_cop * self.opex_fraccion_capex)


@dataclass(frozen=True)
class FilaFlujo:
    anio: int
    ingresos_ahorro_cop: int
    costos_om_cop: int
    flujo_neto_cop: int
    flujo_acumulado_cop: int


def energia_del_anio(p: ParametrosFinancieros, anio: int) -> float:
    """Energía servida en el año `anio` (≥ 1), con la degradación de los módulos."""
    return p.energia_anual_servida_kwh * (1 - p.degradacion_fv_anual) ** (anio - 1)


def costo_diesel_del_anio(p: ParametrosFinancieros, anio: int) -> float:
    return p.costo_diesel_evitado_cop_kwh * (1 + p.escalamiento_diesel) ** (anio - 1)


def costos_del_anio(p: ParametrosFinancieros, anio: int) -> float:
    """O&M del año más el reemplazo de baterías, si cae en ese año."""
    costo = p.opex_anual_cop * (1 + p.inflacion_opex) ** (anio - 1)
    if anio == p.anio_reemplazo_baterias:
        costo += p.reemplazo_baterias_cop
    return costo


def flujo_de_caja(p: ParametrosFinancieros) -> list[FilaFlujo]:
    """Año 0 = inversión; años 1..horizonte = ahorro en diésel menos O&M. Pesos enteros."""
    filas = [FilaFlujo(0, 0, 0, -p.capex_cop, -p.capex_cop)]
    acumulado = -p.capex_cop
    for anio in range(1, p.horizonte_anios + 1):
        ingresos = round(energia_del_anio(p, anio) * costo_diesel_del_anio(p, anio))
        costos = round(costos_del_anio(p, anio))
        neto = ingresos - costos
        acumulado += neto
        filas.append(FilaFlujo(anio, ingresos, costos, neto, acumulado))
    return filas


def vpn(flujos: list[float], tasa: float) -> float:
    return sum(f / (1 + tasa) ** t for t, f in enumerate(flujos))


def tir(flujos: list[float]) -> float:
    """TIR por bisección. Requiere un flujo convencional (inversión inicial y luego positivos
    netos): así el VPN decrece con la tasa y hay una sola raíz en (-99 %, 100 %)."""
    bajo, alto = -0.99, 1.0
    if vpn(flujos, bajo) * vpn(flujos, alto) > 0:
        raise ValueError("El flujo no cambia de signo: la TIR no existe en (-99 %, 100 %).")
    for _ in range(TIR_MAX_ITERACIONES):
        medio = (bajo + alto) / 2
        if vpn(flujos, medio) > 0:
            bajo = medio
        else:
            alto = medio
        if alto - bajo < TIR_TOLERANCIA:
            break
    return (bajo + alto) / 2


def _energia_descontada(p: ParametrosFinancieros) -> float:
    return sum(
        energia_del_anio(p, t) / (1 + p.tasa_descuento) ** t
        for t in range(1, p.horizonte_anios + 1)
    )


def lcoe(p: ParametrosFinancieros) -> float:
    """COP/kWh: (CAPEX + VP de los costos) / VP de la energía, a la tasa de descuento."""
    costos = p.capex_cop + sum(
        costos_del_anio(p, t) / (1 + p.tasa_descuento) ** t for t in range(1, p.horizonte_anios + 1)
    )
    return costos / _energia_descontada(p)


def costo_nivelado_diesel(p: ParametrosFinancieros) -> float:
    """COP/kWh del diésel nivelado con la misma tasa, horizonte y energía que el LCOE.

    Es la referencia justa para el LCOE: comparar un costo nivelado con el precio del año 1
    mezcla magnitudes distintas (OT-0004 §4.8).
    """
    costo = sum(
        energia_del_anio(p, t) * costo_diesel_del_anio(p, t) / (1 + p.tasa_descuento) ** t
        for t in range(1, p.horizonte_anios + 1)
    )
    return costo / _energia_descontada(p)


def payback_anios(filas: list[FilaFlujo]) -> float | None:
    """Payback **simple** (sin descontar): años hasta que el acumulado cruza cero,
    interpolando dentro del año del cruce."""
    for previa, fila in zip(filas, filas[1:], strict=False):
        if previa.flujo_acumulado_cop < 0 <= fila.flujo_acumulado_cop:
            fraccion = -previa.flujo_acumulado_cop / fila.flujo_neto_cop
            return previa.anio + fraccion
    return None


@dataclass(frozen=True)
class Indicadores:
    vpn_cop: int
    tir_porcentaje: float
    lcoe_cop_kwh: float
    costo_nivelado_diesel_cop_kwh: float
    ahorro_anual_diesel_cop: int
    toneladas_co2_evitadas_anual: float
    payback_anios: float | None


def indicadores(p: ParametrosFinancieros, filas: list[FilaFlujo]) -> Indicadores:
    """KPIs calculados del flujo ya redondeado a pesos (el mismo que se guarda)."""
    netos = [f.flujo_neto_cop for f in filas]
    return Indicadores(
        vpn_cop=round(vpn(netos, p.tasa_descuento)),
        tir_porcentaje=round(tir(netos) * 100, 2),
        lcoe_cop_kwh=round(lcoe(p), 2),
        costo_nivelado_diesel_cop_kwh=round(costo_nivelado_diesel(p), 2),
        ahorro_anual_diesel_cop=filas[1].ingresos_ahorro_cop,
        toneladas_co2_evitadas_anual=round(
            p.energia_anual_servida_kwh * p.factor_emision_kgco2_kwh / 1000, 2
        ),
        payback_anios=payback_anios(filas),
    )
