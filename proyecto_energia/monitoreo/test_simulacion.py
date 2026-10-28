"""Invariantes físicas del escenario simulado (OT-0004 §6). Sin base de datos."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from analitica import services as analitica
from monitoreo import simulacion as sim
from monitoreo.management.commands.seed_amalfi_data import PLANTA
from monitoreo.models import ConsumoPorSegmento

BOGOTA = ZoneInfo("America/Bogota")
# Inicio a media tarde, como el comando real (la ventana no empieza a medianoche).
INICIO = datetime(2026, 9, 28, 15, tzinfo=BOGOTA)
HORAS = 30 * 24
TOLERANCIA = 1e-9


class EscenarioBaseTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.escenario = sim.generar_escenario(INICIO, HORAS, 42, PLANTA)
        cls.horas = cls.escenario.horas


class VentanaTests(EscenarioBaseTests):
    def test_720_horas_consecutivas_sin_huecos(self):
        self.assertEqual(len(self.horas), HORAS)
        for previa, siguiente in zip(self.horas, self.horas[1:], strict=False):
            self.assertEqual(siguiente.timestamp - previa.timestamp, timedelta(hours=1))

    def test_misma_semilla_mismo_escenario(self):
        otra = sim.generar_escenario(INICIO, HORAS, 42, PLANTA).horas
        self.assertEqual(
            [(h.generacion_fv_kwh, h.demanda_total_kwh, h.soc_porcentaje) for h in self.horas],
            [(h.generacion_fv_kwh, h.demanda_total_kwh, h.soc_porcentaje) for h in otra],
        )

    def test_otra_semilla_otro_escenario(self):
        otra = sim.generar_escenario(INICIO, HORAS, 7, PLANTA).horas
        self.assertNotEqual(
            [h.generacion_fv_kwh for h in self.horas], [h.generacion_fv_kwh for h in otra]
        )


class ClimaYGeneracionTests(EscenarioBaseTests):
    def test_irradiancia_cero_fuera_de_06_a_18(self):
        for h in self.horas:
            if not sim.HORA_AMANECER <= h.timestamp.hour < sim.HORA_ATARDECER:
                self.assertEqual(h.irradiancia_wm2, 0.0, h.timestamp)

    def test_picos_de_dias_despejados_entre_750_y_1000(self):
        # Sólo fechas que contienen el mediodía: el primer día de la ventana empieza a las 15:00.
        con_mediodia = {h.timestamp.date() for h in self.horas if h.timestamp.hour in (11, 12)}
        picos = {}
        for h in self.horas:
            if h.tipo_dia == sim.DESPEJADO and h.timestamp.date() in con_mediodia:
                fecha = h.timestamp.date()
                picos[fecha] = max(picos.get(fecha, 0.0), h.irradiancia_wm2)
        self.assertTrue(picos, "el escenario debería tener días despejados")
        for fecha, pico in picos.items():
            with self.subTest(fecha=fecha):
                self.assertGreaterEqual(pico, 750)
                self.assertLessEqual(pico, 1000)

    def test_temperaturas_en_rango(self):
        for h in self.horas:
            self.assertGreaterEqual(h.temp_ambiente_c, 17)
            self.assertLessEqual(h.temp_ambiente_c, 30)
            self.assertGreaterEqual(h.temp_panel_c, h.temp_ambiente_c)
            self.assertLessEqual(h.temp_panel_c, 49)

    def test_dia_despejado_va_de_unos_18_a_unos_29_grados(self):
        despejadas = [h.temp_ambiente_c for h in self.horas if h.tipo_dia == sim.DESPEJADO]
        self.assertLess(min(despejadas), 19)
        self.assertGreater(max(despejadas), 28)

    def test_generacion_cero_de_noche_y_acotada_por_la_potencia_pico(self):
        for h in self.horas:
            if h.irradiancia_wm2 == 0:
                self.assertEqual(h.generacion_fv_kwh, 0.0)
            self.assertGreaterEqual(h.generacion_fv_kwh, 0.0)
            self.assertLessEqual(h.generacion_fv_kwh, PLANTA.potencia_pico_kwp)

    def test_frente_lluvioso_de_tres_dias_nublados(self):
        self.assertEqual(len(self.escenario.fechas_frente), sim.DIAS_FRENTE_LLUVIOSO)
        for fecha in self.escenario.fechas_frente:
            self.assertEqual(self.escenario.tipos_dia[fecha], sim.NUBLADO)


class DemandaTests(EscenarioBaseTests):
    def test_segmentos_son_los_del_modelo(self):
        self.assertEqual(set(sim.SEGMENTOS), set(ConsumoPorSegmento.TipoUsuario.values))

    def test_cuatro_segmentos_por_hora(self):
        for h in self.horas:
            self.assertEqual(set(h.segmentos), set(sim.SEGMENTOS))

    def _hora_pico(self, segmento, entre_semana=True):
        """Hora local con mayor consumo medio esperado del segmento."""
        suma = [0.0] * 24
        for h in self.horas:
            if (h.timestamp.weekday() < 5) == entre_semana:
                suma[h.timestamp.hour] += h.segmentos_esperados[segmento]
        return max(range(24), key=suma.__getitem__)

    def test_picos_de_cada_segmento_en_su_ventana(self):
        self.assertIn(self._hora_pico(sim.RESIDENCIAL), range(18, 21))
        self.assertIn(self._hora_pico(sim.PRODUCTIVO), range(9, 15))
        self.assertIn(self._hora_pico(sim.COMUNITARIO), range(8, 16))

    def test_alumbrado_solo_de_18_a_06(self):
        for h in self.horas:
            encendido = h.timestamp.hour >= 18 or h.timestamp.hour < 6
            self.assertEqual(h.segmentos[sim.ALUMBRADO] > 0, encendido, h.timestamp)

    def test_productivo_baja_el_domingo(self):
        def medio(dia_semana):
            valores = [
                h.segmentos_esperados[sim.PRODUCTIVO]
                for h in self.horas
                if h.timestamp.weekday() == dia_semana and h.timestamp.hour == 11
            ]
            return sum(valores) / len(valores)

        self.assertLess(medio(6), medio(2) * 0.3)


class BateriaTests(EscenarioBaseTests):
    def test_soc_entre_15_y_100(self):
        for h in self.horas:
            self.assertGreaterEqual(h.soc_porcentaje, PLANTA.soc_minimo_pct)
            self.assertLessEqual(h.soc_porcentaje, PLANTA.soc_maximo_pct)

    def test_cada_cambio_de_soc_cuadra_con_la_potencia_y_las_eficiencias(self):
        soc_previo = PLANTA.soc_inicial_pct
        for h in self.horas:
            p = h.potencia_bateria_kw
            energia_almacenada = (
                p * PLANTA.eficiencia_carga if p >= 0 else p / PLANTA.eficiencia_descarga
            )
            esperado = soc_previo + energia_almacenada / PLANTA.capacidad_bateria_kwh * 100
            self.assertAlmostEqual(h.soc_porcentaje, esperado, delta=1e-6)
            soc_previo = h.soc_porcentaje

    def test_balance_horario_cierra(self):
        """generación + descarga + no suministrada = demanda + carga + vertimiento."""
        for h in self.horas:
            entra = h.generacion_fv_kwh + max(-h.potencia_bateria_kw, 0)
            entra += h.energia_no_suministrada_kwh
            sale = h.demanda_total_kwh + max(h.potencia_bateria_kw, 0) + h.vertimiento_kwh
            self.assertAlmostEqual(entra, sale, delta=TOLERANCIA)

    def test_estado_cuadra_con_los_umbrales(self):
        for h in self.horas:
            self.assertEqual(h.estado_sistema, sim.estado_por_soc(h.soc_porcentaje, PLANTA))

    def test_aparecen_los_tres_estados(self):
        self.assertEqual(
            {h.estado_sistema for h in self.horas},
            {sim.ESTADO_OPTIMO, sim.ESTADO_ALERTA, sim.ESTADO_CRITICO},
        )

    def test_autonomia_cero_en_la_reserva_y_positiva_por_encima(self):
        for h in self.horas:
            if h.soc_porcentaje <= PLANTA.soc_minimo_pct + TOLERANCIA:
                self.assertAlmostEqual(h.autonomia_horas, 0.0, delta=1e-6)
            else:
                self.assertGreater(h.autonomia_horas, 0)

    def test_potencia_dentro_del_limite(self):
        for h in self.horas:
            self.assertLessEqual(abs(h.potencia_bateria_kw), PLANTA.potencia_max_bateria_kw)


class PrediccionYAnomaliasTests(EscenarioBaseTests):
    def test_error_de_prediccion_entre_3_y_8_por_ciento_en_horas_normales(self):
        for h in self.horas:
            if h.anomalia_inyectada:
                continue
            for real, predicho in (
                (h.generacion_esperada_kwh, h.generacion_predicha_kwh),
                (h.demanda_esperada_kwh, h.demanda_predicha_kwh),
            ):
                if real > 0:
                    error = abs(predicho / real - 1)
                    self.assertGreaterEqual(error, analitica.ERROR_PREDICCION_MIN - TOLERANCIA)
                    self.assertLessEqual(error, analitica.ERROR_PREDICCION_MAX + TOLERANCIA)

    def test_de_noche_la_generacion_predicha_es_cero(self):
        for h in self.horas:
            if h.irradiancia_wm2 == 0:
                self.assertEqual(h.generacion_predicha_kwh, 0.0)

    def test_entre_6_y_8_anomalias_con_los_tipos_obligatorios(self):
        tipos = [a.tipo for a in self.escenario.anomalias]
        self.assertGreaterEqual(len(tipos), analitica.ANOMALIAS_MIN)
        self.assertLessEqual(len(tipos), analitica.ANOMALIAS_MAX)
        self.assertTrue(set(analitica.TIPOS_OBLIGATORIOS) <= set(tipos))

    def test_anomalias_en_dias_distintos_y_fuera_del_frente(self):
        fechas = [self.horas[a.indice].timestamp.date() for a in self.escenario.anomalias]
        self.assertEqual(len(fechas), len(set(fechas)))
        self.assertFalse(set(fechas) & set(self.escenario.fechas_frente))

    def test_la_anomalia_se_refleja_en_el_dato_real(self):
        for a in self.escenario.anomalias:
            h = self.horas[a.indice]
            if a.tipo in (analitica.FALLA_INVERSOR, analitica.SOMBREADO_PARCIAL):
                self.assertLess(h.generacion_fv_kwh, h.generacion_esperada_kwh)
            else:
                self.assertGreater(h.demanda_total_kwh, h.demanda_esperada_kwh)


class RobustezEntreSemillasTests(SimpleTestCase):
    """Lo que el dashboard promete no puede depender de la suerte de la semilla 42."""

    SEMILLAS = range(1, 31)

    def test_invariantes_clave_en_30_semillas(self):
        for semilla in self.SEMILLAS:
            with self.subTest(semilla=semilla):
                escenario = sim.generar_escenario(INICIO, HORAS, semilla, PLANTA)
                horas = escenario.horas
                self.assertEqual(
                    {h.estado_sistema for h in horas},
                    {sim.ESTADO_OPTIMO, sim.ESTADO_ALERTA, sim.ESTADO_CRITICO},
                )
                inyectadas = {(a.indice, a.tipo) for a in escenario.anomalias}
                detectadas = {(i, h.deteccion.tipo) for i, h in enumerate(horas) if h.deteccion}
                # Control negativo incluido: ninguna hora normal marcada, ninguna anomalía perdida.
                self.assertEqual(detectadas, inyectadas)
                self.assertIn(
                    len(inyectadas), range(analitica.ANOMALIAS_MIN, analitica.ANOMALIAS_MAX + 1)
                )
