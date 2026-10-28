import random
from datetime import date

from django.test import SimpleTestCase

from . import services as s


class PrediccionTests(SimpleTestCase):
    def test_error_acotado_y_con_ambos_signos(self):
        rng = random.Random(0)
        errores = [s.predecir(100.0, rng) / 100.0 - 1 for _ in range(500)]
        for e in errores:
            self.assertGreaterEqual(abs(e), s.ERROR_PREDICCION_MIN)
            self.assertLessEqual(abs(e), s.ERROR_PREDICCION_MAX)
        self.assertTrue(any(e > 0 for e in errores) and any(e < 0 for e in errores))

    def test_valor_cero_se_predice_cero(self):
        self.assertEqual(s.predecir(0.0, random.Random(0)), 0.0)


class DetectorTests(SimpleTestCase):
    def test_hora_normal_no_dispara(self):
        self.assertIsNone(s.detectar(12, 35.0, 37.0, 12.0, 11.5))

    def test_caida_casi_total_es_falla_de_inversor(self):
        d = s.detectar(12, 2.0, 35.0, 12.0, 12.0)
        self.assertEqual(d.tipo, s.FALLA_INVERSOR)
        self.assertIn("12:00", d.descripcion)
        self.assertIn("2,0 kWh", d.descripcion)

    def test_caida_parcial_es_sombreado(self):
        self.assertEqual(s.detectar(11, 17.0, 34.0, 12.0, 12.0).tipo, s.SOMBREADO_PARCIAL)

    def test_pico_diurno_y_consumo_nocturno(self):
        self.assertEqual(s.detectar(10, 0.0, 0.0, 22.0, 13.0).tipo, s.PICO_CONSUMO)
        self.assertEqual(s.detectar(2, 0.0, 0.0, 7.0, 3.3).tipo, s.CONSUMO_NOCTURNO_ATIPICO)

    def test_desviacion_relativa_grande_pero_absoluta_pequena_no_dispara(self):
        # +50 % pero sólo 1 kWh: ruido de una carga pequeña, no una anomalía.
        self.assertIsNone(s.detectar(3, 0.0, 0.0, 3.0, 2.0))

    def test_desviaciones_en_sentido_opuesto_tambien_se_reportan(self):
        self.assertEqual(s.detectar(12, 30.0, 10.0, 12.0, 12.0).tipo, s.GENERACION_ATIPICA)
        self.assertEqual(s.detectar(12, 0.0, 0.0, 4.0, 12.0).tipo, s.CAIDA_DEMANDA)


class PlanAnomaliasTests(SimpleTestCase):
    def test_sin_dias_compatibles_falla_con_mensaje(self):
        nublados = [(date(2026, 10, d), False, True) for d in range(1, 10)]
        with self.assertRaisesMessage(ValueError, "amplía --dias"):
            s.planear_anomalias(nublados, random.Random(0))


class MetricasTests(SimpleTestCase):
    def test_valores_conocidos(self):
        reales, predichos = [1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 6.0]
        self.assertAlmostEqual(s.mae(reales, predichos), 0.5)
        self.assertAlmostEqual(s.rmse(reales, predichos), 1.0)
        # SS_tot = 5, SS_res = 4 → R² = 0,2
        self.assertAlmostEqual(s.r2(reales, predichos), 0.2)

    def test_prediccion_perfecta(self):
        self.assertEqual(s.r2([1.0, 2.0], [1.0, 2.0]), 1.0)

    def test_r2_sin_varianza_es_none(self):
        self.assertIsNone(s.r2([5.0, 5.0], [4.0, 6.0]))


class PlanAnomaliasVentanaCortaTests(SimpleTestCase):
    def test_extras_sin_dia_de_sol_se_degradan_a_nocturnos(self):
        # 2 días con sol (para los dos obligatorios que lo exigen) y el resto nublados.
        dias = [(date(2026, 10, 1), True, True), (date(2026, 10, 2), True, True)]
        dias += [(date(2026, 10, d), False, True) for d in range(3, 12)]
        for semilla in range(50):
            plan = s.planear_anomalias(dias, random.Random(semilla))
            tipos = [p[1] for p in plan]
            self.assertTrue(set(s.TIPOS_OBLIGATORIOS) <= set(tipos))
            self.assertEqual(len({p[0] for p in plan}), len(plan))
