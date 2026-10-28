"""Simulación física horaria de la microrred de Amalfi (lógica pura, sin ORM).

Con pasos de 1 h, la energía de una hora (kWh) y la potencia media de esa hora (kW) son el
mismo número. Los parámetros de la planta llegan como `ParametrosPlanta` desde la cabecera de
`seed_amalfi_data.py`; aquí viven el clima del sitio y los perfiles de carga.
"""

import math
import random
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from analitica import services as analitica

# ── Clima de Amalfi (andino húmedo, ~1 550 m s. n. m.) ─────────────────────────────────────
HORA_AMANECER, HORA_ATARDECER = 6, 18
IRRADIANCIA_MAXIMA_WM2 = 1000.0
IRRADIANCIA_PICO_DIA_WM2 = (850.0, 1000.0)  # cielo claro al mediodía, varía día a día
TEMP_MIN_C, HORA_TEMP_MIN = 18.0, 5
TEMP_MAX_C, HORA_TEMP_MAX = 29.0, 14
RUIDO_TEMP_C = 0.4

DESPEJADO, PARCIAL, NUBLADO = "DESPEJADO", "PARCIAL", "NUBLADO"
# Fracción de la irradiancia de cielo claro que llega en el día, según su tipo.
FACTOR_NUBOSIDAD_DIA = {DESPEJADO: (0.95, 1.0), PARCIAL: (0.65, 0.85), NUBLADO: (0.30, 0.50)}
# Ruido horario (mañana, tarde): la convección andina nubla sobre todo las tardes.
HORA_INICIO_TARDE = 13
RUIDO_NUBOSIDAD_HORA = {
    DESPEJADO: ((0.97, 1.03), (0.97, 1.03)),
    PARCIAL: ((0.85, 1.05), (0.45, 0.95)),
    NUBLADO: ((0.60, 1.20), (0.50, 1.10)),
}
# Amplitud térmica relativa: un día nublado no se calienta tanto ni se enfría tanto.
AMPLITUD_TERMICA = {DESPEJADO: 1.0, PARCIAL: 0.8, NUBLADO: 0.5}
# Cadena de Markov del tipo de día (persistencia del tiempo atmosférico).
TRANSICIONES_DIA = {
    DESPEJADO: {DESPEJADO: 0.45, PARCIAL: 0.45, NUBLADO: 0.10},
    PARCIAL: {DESPEJADO: 0.30, PARCIAL: 0.45, NUBLADO: 0.25},
    NUBLADO: {DESPEJADO: 0.15, PARCIAL: 0.45, NUBLADO: 0.40},
}
# Frente lluvioso forzado: representa la temporada de lluvias (octubre) con un episodio de
# varios días seguidos de déficit. No es lo que produce ALERTA/CRITICO —medido: sin él, las 30
# semillas de prueba los muestran igual—; las anomalías se inyectan fuera de él para que se lean
# claras frente a un día ya anómalo.
DIAS_FRENTE_LLUVIOSO = 3

# ── Perfiles de carga (kWh por hora local 0..23, día entre semana) ──────────────────────────
RESIDENCIAL, PRODUCTIVO, COMUNITARIO, ALUMBRADO = (
    "RESIDENCIAL",
    "PRODUCTIVO",
    "COMUNITARIO",
    "ALUMBRADO",
)
SEGMENTOS = (RESIDENCIAL, PRODUCTIVO, COMUNITARIO, ALUMBRADO)
# ~60 viviendas: base nocturna, rampa de la mañana y pico de 18:00 a 21:00 (≈ 72 kWh/día).
PERFIL_RESIDENCIAL = [1.2] * 5 + [2.5, 3.5, 3.0] + [2.0] * 4 + [2.5] + [2.0] * 4 + [4.0]
PERFIL_RESIDENCIAL += [8.0, 9.0, 8.5, 5.0, 2.5, 1.5]
# Trapiche y beneficiadero: pico de 09:00 a 15:00 (≈ 58 kWh/día).
PERFIL_PRODUCTIVO = [0.3] * 7 + [1.0, 3.0] + [7.5] * 6 + [3.0, 1.5, 0.8] + [0.3] * 6
# Escuela y puesto de salud: 08:00 a 16:00; refrigeración de vacunas como base (≈ 29 kWh/día).
PERFIL_COMUNITARIO = [0.25] * 7 + [0.8] + [3.0] * 8 + [0.8] + [0.25] * 7
PERFIL_COMUNITARIO_FIN_DE_SEMANA = [0.25] * 24
# Luminarias LED: carga fija de 18:00 a 06:00 (≈ 18 kWh/día).
PERFIL_ALUMBRADO = [1.5] * 6 + [0.0] * 12 + [1.5] * 6
# Actividad productiva por día de la semana (lunes = 0).
FACTOR_PRODUCTIVO_SEMANA = [1.0, 1.0, 1.0, 1.0, 1.0, 0.6, 0.15]
RUIDO_CARGA = (0.90, 1.10)

ESTADO_OPTIMO, ESTADO_ALERTA, ESTADO_CRITICO = "OPTIMO", "ALERTA", "CRITICO"
HORAS_MEDIA_MOVIL_AUTONOMIA = 24


@dataclass(frozen=True)
class ParametrosPlanta:
    potencia_pico_kwp: float
    coef_temperatura_potencia: float  # 1/°C, negativo
    eficiencia_bos: float  # inversor, cableado, suciedad
    coef_calentamiento_panel: float  # °C por W/m²
    capacidad_bateria_kwh: float
    soc_inicial_pct: float
    soc_minimo_pct: float
    soc_maximo_pct: float
    eficiencia_carga: float
    eficiencia_descarga: float
    potencia_max_bateria_kw: float
    umbral_optimo_pct: float  # SoC ≥ umbral → OPTIMO
    umbral_alerta_pct: float  # umbral ≤ SoC < óptimo → ALERTA; menor → CRITICO


@dataclass
class HoraSimulada:
    timestamp: datetime
    tipo_dia: str
    irradiancia_wm2: float
    temp_ambiente_c: float
    temp_panel_c: float
    generacion_esperada_kwh: float
    segmentos_esperados: dict[str, float]
    generacion_fv_kwh: float = 0.0
    segmentos: dict[str, float] = field(default_factory=dict)
    soc_porcentaje: float = 0.0
    potencia_bateria_kw: float = 0.0
    vertimiento_kwh: float = 0.0
    energia_no_suministrada_kwh: float = 0.0
    autonomia_horas: float = 0.0
    estado_sistema: str = ""
    generacion_predicha_kwh: float = 0.0
    demanda_predicha_kwh: float = 0.0
    anomalia_inyectada: str | None = None
    deteccion: analitica.Deteccion | None = None

    @property
    def demanda_total_kwh(self) -> float:
        return sum(self.segmentos.values())

    @property
    def demanda_esperada_kwh(self) -> float:
        return sum(self.segmentos_esperados.values())


@dataclass
class Escenario:
    horas: list[HoraSimulada]
    tipos_dia: dict[date, str]
    fechas_frente: list[date]
    anomalias: list[analitica.AnomaliaInyectada]


# ── Clima ────────────────────────────────────────────────────────────────────────────────
def tipos_de_dia(fechas: list[date], fechas_completas: list[date], rng: random.Random):
    """Tipo de día por fecha (Markov) más un frente lluvioso forzado sobre fechas completas."""
    tipos = {}
    estado = rng.choice((DESPEJADO, PARCIAL))
    for fecha in fechas:
        tipos[fecha] = estado
        destinos = TRANSICIONES_DIA[estado]
        estado = rng.choices(list(destinos), weights=list(destinos.values()))[0]
    frente = []
    # Margen de 2 días a cada lado: la batería entra cargada al frente y alcanza a recuperarse.
    if len(fechas_completas) >= DIAS_FRENTE_LLUVIOSO + 4:
        inicio = rng.randint(2, len(fechas_completas) - DIAS_FRENTE_LLUVIOSO - 2)
        frente = fechas_completas[inicio : inicio + DIAS_FRENTE_LLUVIOSO]
        for fecha in frente:
            tipos[fecha] = NUBLADO
    return tipos, frente


def irradiancia(hora: int, pico_dia: float, factor_dia: float, ruido: float) -> float:
    """Campana senoidal entre amanecer y atardecer, evaluada en la mitad de la hora."""
    if not HORA_AMANECER <= hora < HORA_ATARDECER:
        return 0.0
    fase = math.pi * (hora + 0.5 - HORA_AMANECER) / (HORA_ATARDECER - HORA_AMANECER)
    return min(pico_dia * factor_dia * math.sin(fase) * ruido, IRRADIANCIA_MAXIMA_WM2)


def temperatura_ambiente(hora: int, tipo_dia: str) -> float:
    """Coseno ascendente del mínimo (05:00) al máximo (14:00) y descendente el resto del día."""
    media = (TEMP_MIN_C + TEMP_MAX_C) / 2
    semiamplitud = (TEMP_MAX_C - TEMP_MIN_C) / 2 * AMPLITUD_TERMICA[tipo_dia]
    if HORA_TEMP_MIN <= hora <= HORA_TEMP_MAX:
        forma = (
            1 - math.cos(math.pi * (hora - HORA_TEMP_MIN) / (HORA_TEMP_MAX - HORA_TEMP_MIN))
        ) / 2
    else:
        horas_de_bajada = 24 - (HORA_TEMP_MAX - HORA_TEMP_MIN)
        transcurridas = (hora - HORA_TEMP_MAX) % 24
        forma = 1 - (1 - math.cos(math.pi * transcurridas / horas_de_bajada)) / 2
    return media - semiamplitud + 2 * semiamplitud * forma


def temperatura_panel(temp_ambiente: float, irradiancia_wm2: float, planta: ParametrosPlanta):
    return temp_ambiente + planta.coef_calentamiento_panel * irradiancia_wm2


def generacion_fv(irradiancia_wm2: float, temp_panel: float, planta: ParametrosPlanta) -> float:
    """kWh en la hora: potencia pico × irradiancia relativa × pérdida térmica × pérdidas BOS."""
    perdida_termica = 1 + planta.coef_temperatura_potencia * (temp_panel - 25)
    return (
        planta.potencia_pico_kwp
        * (irradiancia_wm2 / IRRADIANCIA_MAXIMA_WM2)
        * perdida_termica
        * planta.eficiencia_bos
    )


# ── Demanda ──────────────────────────────────────────────────────────────────────────────
def demanda_por_segmento(momento: datetime, rng: random.Random) -> dict[str, float]:
    hora, dia_semana = momento.hour, momento.weekday()
    fin_de_semana = dia_semana >= 5
    comunitario = PERFIL_COMUNITARIO_FIN_DE_SEMANA if fin_de_semana else PERFIL_COMUNITARIO
    return {
        RESIDENCIAL: PERFIL_RESIDENCIAL[hora] * rng.uniform(*RUIDO_CARGA),
        PRODUCTIVO: PERFIL_PRODUCTIVO[hora]
        * FACTOR_PRODUCTIVO_SEMANA[dia_semana]
        * rng.uniform(*RUIDO_CARGA),
        COMUNITARIO: comunitario[hora] * rng.uniform(*RUIDO_CARGA),
        ALUMBRADO: PERFIL_ALUMBRADO[hora],
    }


# ── Batería ──────────────────────────────────────────────────────────────────────────────
def estado_por_soc(soc: float, planta: ParametrosPlanta) -> str:
    if soc >= planta.umbral_optimo_pct:
        return ESTADO_OPTIMO
    if soc >= planta.umbral_alerta_pct:
        return ESTADO_ALERTA
    return ESTADO_CRITICO


def despachar_bateria(horas: list[HoraSimulada], planta: ParametrosPlanta) -> None:
    """Despacho hora a hora: el excedente carga, el déficit descarga, dentro de los límites.

    Lo que no cabe en la batería llena es vertimiento; lo que no cubre la batería en su
    reserva mínima es energía no suministrada. `potencia_bateria_kw` es la potencia en el
    lado AC: positiva al cargar, negativa al descargar.
    """
    capacidad = planta.capacidad_bateria_kwh
    soc = planta.soc_inicial_pct
    demanda_reciente = deque(maxlen=HORAS_MEDIA_MOVIL_AUTONOMIA)
    for h in horas:
        neto = h.generacion_fv_kwh - h.demanda_total_kwh
        if neto >= 0:
            admisible = (planta.soc_maximo_pct - soc) / 100 * capacidad / planta.eficiencia_carga
            carga = min(neto, planta.potencia_max_bateria_kw, admisible)
            soc += carga * planta.eficiencia_carga / capacidad * 100
            h.potencia_bateria_kw = carga
            h.vertimiento_kwh = neto - carga
        else:
            entregable = (
                (soc - planta.soc_minimo_pct) / 100 * capacidad * planta.eficiencia_descarga
            )
            descarga = min(-neto, planta.potencia_max_bateria_kw, entregable)
            soc -= descarga / planta.eficiencia_descarga / capacidad * 100
            h.potencia_bateria_kw = -descarga
            h.energia_no_suministrada_kwh = -neto - descarga
        # Sólo absorbe el error de redondeo en coma flotante; los límites ya se respetaron arriba.
        soc = min(max(soc, planta.soc_minimo_pct), planta.soc_maximo_pct)
        h.soc_porcentaje = soc
        h.estado_sistema = estado_por_soc(soc, planta)
        demanda_reciente.append(h.demanda_total_kwh)
        demanda_media = sum(demanda_reciente) / len(demanda_reciente)
        energia_util = (soc - planta.soc_minimo_pct) / 100 * capacidad * planta.eficiencia_descarga
        h.autonomia_horas = energia_util / demanda_media if demanda_media > 0 else 0.0


# ── Escenario completo ───────────────────────────────────────────────────────────────────
def generar_escenario(
    inicio: datetime, horas_totales: int, semilla: int, planta: ParametrosPlanta
) -> Escenario:
    """Clima → generación y demanda esperadas → anomalías → batería → predicción → detección.

    `inicio` debe ser *aware* en la zona horaria local: los perfiles usan la hora local.
    Misma semilla y mismo inicio → mismo escenario.
    """
    rng = random.Random(semilla)
    momentos = [inicio + timedelta(hours=i) for i in range(horas_totales)]
    fechas = sorted({m.date() for m in momentos})
    horas_por_fecha = {f: sum(1 for m in momentos if m.date() == f) for f in fechas}
    fechas_completas = [f for f in fechas if horas_por_fecha[f] == 24]

    tipos, frente = tipos_de_dia(fechas, fechas_completas, rng)
    pico_dia = {f: rng.uniform(*IRRADIANCIA_PICO_DIA_WM2) for f in fechas}
    factor_dia = {f: rng.uniform(*FACTOR_NUBOSIDAD_DIA[tipos[f]]) for f in fechas}

    horas = []
    for momento in momentos:
        tipo = tipos[momento.date()]
        manana, tarde = RUIDO_NUBOSIDAD_HORA[tipo]
        ruido = rng.uniform(*(tarde if momento.hour >= HORA_INICIO_TARDE else manana))
        g = irradiancia(momento.hour, pico_dia[momento.date()], factor_dia[momento.date()], ruido)
        t_amb = temperatura_ambiente(momento.hour, tipo) + rng.uniform(-RUIDO_TEMP_C, RUIDO_TEMP_C)
        t_panel = temperatura_panel(t_amb, g, planta)
        segmentos = demanda_por_segmento(momento, rng)
        generacion = generacion_fv(g, t_panel, planta)
        horas.append(
            HoraSimulada(
                timestamp=momento,
                tipo_dia=tipo,
                irradiancia_wm2=g,
                temp_ambiente_c=t_amb,
                temp_panel_c=t_panel,
                generacion_esperada_kwh=generacion,
                segmentos_esperados=segmentos,
                generacion_fv_kwh=generacion,
                segmentos=dict(segmentos),
            )
        )

    # Anomalías: en fechas completas, fuera del frente lluvioso, una por fecha.
    indice = {(h.timestamp.date(), h.timestamp.hour): i for i, h in enumerate(horas)}
    candidatos = [
        (f, tipos[f] != NUBLADO, f.weekday() < 5) for f in fechas_completas if f not in frente
    ]
    anomalias = []
    for fecha, tipo, hora, factor in analitica.planear_anomalias(candidatos, rng):
        i = indice[(fecha, hora)]
        h = horas[i]
        if tipo in (analitica.FALLA_INVERSOR, analitica.SOMBREADO_PARCIAL):
            h.generacion_fv_kwh = h.generacion_esperada_kwh * factor
        elif tipo == analitica.PICO_CONSUMO:
            h.segmentos[PRODUCTIVO] = h.segmentos_esperados[PRODUCTIVO] * factor
        else:
            h.segmentos[RESIDENCIAL] = h.segmentos_esperados[RESIDENCIAL] * factor
        h.anomalia_inyectada = tipo
        anomalias.append(analitica.AnomaliaInyectada(i, tipo, factor))

    despachar_bateria(horas, planta)

    for h in horas:
        h.generacion_predicha_kwh = analitica.predecir(h.generacion_esperada_kwh, rng)
        h.demanda_predicha_kwh = analitica.predecir(h.demanda_esperada_kwh, rng)
        h.deteccion = analitica.detectar(
            h.timestamp.hour,
            h.generacion_fv_kwh,
            h.generacion_predicha_kwh,
            h.demanda_total_kwh,
            h.demanda_predicha_kwh,
        )

    return Escenario(horas, tipos, frente, anomalias)
