"""Predicción mock, anomalías y métricas de error (lógica pura, sin ORM).

Las «predicciones ML» del MVP son el valor físico esperado más un error acotado (ADR-0001).
`es_anomalia` lo decide el detector, no la inyección: la tabla muestra lo que vería un
sistema real, y las pruebas exigen que lo detectado coincida con lo inyectado.
"""

import math
import random
from dataclasses import dataclass

# Error de la predicción mock: |predicho / esperado − 1| ∈ [3 %, 8 %], con signo aleatorio.
ERROR_PREDICCION_MIN = 0.03
ERROR_PREDICCION_MAX = 0.08

# Detector: una hora es anómala si se desvía más del 30 % del valor predicho y más de 2 kWh.
# Con un error de predicción ≤ 8 %, sólo puede disparar en lo inyectado.
UMBRAL_DESVIACION_RELATIVA = 0.30
UMBRAL_DESVIACION_ABSOLUTA_KWH = 2.0
# Una caída de generación de al menos el 85 % es un disparo del inversor; menor, sombreado.
CAIDA_MINIMA_FALLA_INVERSOR = 0.85
HORAS_NOCTURNAS = range(0, 6)

FALLA_INVERSOR = "FALLA_INVERSOR"
SOMBREADO_PARCIAL = "SOMBREADO_PARCIAL"
PICO_CONSUMO = "PICO_CONSUMO"
CONSUMO_NOCTURNO_ATIPICO = "CONSUMO_NOCTURNO_ATIPICO"
GENERACION_ATIPICA = "GENERACION_ATIPICA"
CAIDA_DEMANDA = "CAIDA_DEMANDA"

# Número de anomalías inyectadas en la ventana, y las que deben aparecer al menos una vez.
ANOMALIAS_MIN, ANOMALIAS_MAX = 6, 8
TIPOS_OBLIGATORIOS = (FALLA_INVERSOR, SOMBREADO_PARCIAL, PICO_CONSUMO)
TIPOS_INYECTABLES = (*TIPOS_OBLIGATORIOS, CONSUMO_NOCTURNO_ATIPICO)


@dataclass(frozen=True)
class ReglaInyeccion:
    horas: range  # horas locales candidatas
    factor: tuple[float, float]  # multiplicador aplicado al valor esperado
    solo_dias_con_sol: bool = False
    solo_entre_semana: bool = False


REGLAS_INYECCION = {
    # Generación → 0–10 % del esperado al mediodía.
    FALLA_INVERSOR: ReglaInyeccion(range(10, 14), (0.0, 0.10), solo_dias_con_sol=True),
    # Generación −40 a −60 %, en la mañana (antes de la nubosidad convectiva de la tarde).
    SOMBREADO_PARCIAL: ReglaInyeccion(range(10, 13), (0.40, 0.60), solo_dias_con_sol=True),
    # Demanda productiva ×2,0–2,8: arranque simultáneo de motores del trapiche.
    PICO_CONSUMO: ReglaInyeccion(range(9, 15), (2.0, 2.8), solo_entre_semana=True),
    # Demanda residencial ×3,5–4,5 de madrugada: posible conexión irregular.
    CONSUMO_NOCTURNO_ATIPICO: ReglaInyeccion(range(1, 4), (3.5, 4.5)),
}


@dataclass(frozen=True)
class AnomaliaInyectada:
    indice: int  # posición de la hora en la serie
    tipo: str
    factor: float


@dataclass(frozen=True)
class Deteccion:
    tipo: str
    descripcion: str


def predecir(valor_esperado: float, rng: random.Random) -> float:
    """Predicción mock: el esperado con un error relativo de 3–8 % y signo aleatorio."""
    if valor_esperado == 0:
        return 0.0
    error = rng.uniform(ERROR_PREDICCION_MIN, ERROR_PREDICCION_MAX)
    return valor_esperado * (1 + rng.choice((-1, 1)) * error)


def planear_anomalias(dias_candidatos, rng: random.Random):
    """Elige 6–8 (día, tipo, hora, factor), un día distinto por anomalía.

    `dias_candidatos` es una lista de (fecha, tiene_sol, es_entre_semana). Van primero los
    tipos obligatorios y después los extra con más restricciones. Un extra sin día compatible
    (p. ej., una ventana corta con pocos días de sol) se degrada a consumo nocturno, que cabe
    en cualquier día; sólo un obligatorio sin día compatible es un error.
    """

    def compatibles_con(regla, dias):
        return [
            d
            for d in dias
            if (d[1] or not regla.solo_dias_con_sol) and (d[2] or not regla.solo_entre_semana)
        ]

    def restricciones(tipo):
        regla = REGLAS_INYECCION[tipo]
        return regla.solo_dias_con_sol + regla.solo_entre_semana

    n = rng.randint(ANOMALIAS_MIN, ANOMALIAS_MAX)
    extras = [rng.choice(TIPOS_INYECTABLES) for _ in range(n - len(TIPOS_OBLIGATORIOS))]
    tipos = [*TIPOS_OBLIGATORIOS, *sorted(extras, key=lambda t: -restricciones(t))]
    libres = list(dias_candidatos)
    rng.shuffle(libres)
    plan = []
    for posicion, tipo in enumerate(tipos):
        regla = REGLAS_INYECCION[tipo]
        compatibles = compatibles_con(regla, libres)
        # Por posición, no por nombre: un extra puede ser del mismo tipo que un obligatorio.
        es_extra = posicion >= len(TIPOS_OBLIGATORIOS)
        if not compatibles and es_extra:
            tipo = CONSUMO_NOCTURNO_ATIPICO
            regla = REGLAS_INYECCION[tipo]
            compatibles = compatibles_con(regla, libres)
        if not compatibles:
            raise ValueError(f"No quedan días compatibles para inyectar {tipo}; amplía --dias.")
        dia = compatibles[0]
        libres.remove(dia)
        hora = rng.choice(regla.horas)
        factor = rng.uniform(*regla.factor)
        plan.append((dia[0], tipo, hora, factor))
    return plan


def _num(valor: float) -> str:
    """Número con coma decimal (es-CO)."""
    return f"{valor:.1f}".replace(".", ",")


def _desvia(real: float, predicho: float) -> bool:
    diferencia = abs(real - predicho)
    return (
        predicho > 0
        and diferencia / predicho > UMBRAL_DESVIACION_RELATIVA
        and diferencia > UMBRAL_DESVIACION_ABSOLUTA_KWH
    )


def detectar(
    hora_local: int,
    generacion_real: float,
    generacion_predicha: float,
    demanda_real: float,
    demanda_predicha: float,
) -> Deteccion | None:
    """Regla del detector sobre una hora. Devuelve el diagnóstico o None si es normal."""
    hora = f"{hora_local:02d}:00"
    if _desvia(generacion_real, generacion_predicha):
        variacion = generacion_real / generacion_predicha - 1
        cifras = (
            f"Generación real {_num(generacion_real)} kWh vs. {_num(generacion_predicha)} kWh "
            f"predichos ({variacion * 100:+.0f} %) a las {hora}."
        )
        if variacion <= -CAIDA_MINIMA_FALLA_INVERSOR:
            return Deteccion(FALLA_INVERSOR, f"{cifras} Posible disparo o falla del inversor.")
        if variacion < 0:
            return Deteccion(
                SOMBREADO_PARCIAL, f"{cifras} Posible sombreado parcial o suciedad en módulos."
            )
        return Deteccion(GENERACION_ATIPICA, f"{cifras} Generación por encima de lo esperado.")
    if _desvia(demanda_real, demanda_predicha):
        variacion = demanda_real / demanda_predicha - 1
        cifras = (
            f"Demanda real {_num(demanda_real)} kWh vs. {_num(demanda_predicha)} kWh "
            f"predichos ({variacion * 100:+.0f} %) a las {hora}."
        )
        if variacion < 0:
            return Deteccion(CAIDA_DEMANDA, f"{cifras} Posible desconexión de cargas.")
        if hora_local in HORAS_NOCTURNAS:
            return Deteccion(
                CONSUMO_NOCTURNO_ATIPICO,
                f"{cifras} Consumo nocturno atípico: posible conexión irregular o fuga.",
            )
        return Deteccion(
            PICO_CONSUMO, f"{cifras} Pico atípico: posible arranque simultáneo de motores."
        )
    return None


def mae(reales: list[float], predichos: list[float]) -> float:
    return sum(abs(r - p) for r, p in zip(reales, predichos, strict=True)) / len(reales)


def rmse(reales: list[float], predichos: list[float]) -> float:
    cuadrados = sum((r - p) ** 2 for r, p in zip(reales, predichos, strict=True))
    return math.sqrt(cuadrados / len(reales))


def r2(reales: list[float], predichos: list[float]) -> float | None:
    """Coeficiente de determinación; None si la serie real es constante (sin varianza)."""
    media = sum(reales) / len(reales)
    total = sum((r - media) ** 2 for r in reales)
    if total == 0:
        return None
    residual = sum((r - p) ** 2 for r, p in zip(reales, predichos, strict=True))
    return 1 - residual / total
