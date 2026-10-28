from dataclasses import replace

from django.test import SimpleTestCase

from monitoreo.management.commands.seed_amalfi_data import FINANZAS

from . import calculos as c


class FormulasTests(SimpleTestCase):
    def test_vpn_y_tir_de_un_caso_de_libro(self):
        flujos = [-100.0, 110.0]
        self.assertAlmostEqual(c.vpn(flujos, 0.10), 0.0)
        self.assertAlmostEqual(c.tir(flujos), 0.10, places=6)

    def test_tir_sin_cambio_de_signo_falla(self):
        with self.assertRaises(ValueError):
            c.tir([100.0, 10.0])

    def test_payback_interpolado(self):
        filas = [
            c.FilaFlujo(0, 0, 0, -100, -100),
            c.FilaFlujo(1, 60, 0, 60, -40),
            c.FilaFlujo(2, 80, 0, 80, 40),
        ]
        self.assertAlmostEqual(c.payback_anios(filas), 1.5)

    def test_sin_recuperacion_no_hay_payback(self):
        self.assertIsNone(c.payback_anios([c.FilaFlujo(0, 0, 0, -1, -1)]))


class CasoAmalfiTests(SimpleTestCase):
    """Los supuestos de la cabecera del seeder cumplen las metas del caso de estudio."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.filas = c.flujo_de_caja(FINANZAS)
        cls.kpis = c.indicadores(FINANZAS, cls.filas)

    def test_26_anios_y_acumulado_es_la_suma_corrida(self):
        self.assertEqual([f.anio for f in self.filas], list(range(26)))
        acumulado = 0
        for f in self.filas:
            if f.anio > 0:
                self.assertEqual(f.flujo_neto_cop, f.ingresos_ahorro_cop - f.costos_om_cop)
            acumulado += f.flujo_neto_cop
            self.assertEqual(f.flujo_acumulado_cop, acumulado)

    def test_anio_cero_es_la_inversion(self):
        self.assertEqual(self.filas[0].flujo_neto_cop, -FINANZAS.capex_cop)

    def test_reemplazo_de_baterias_es_el_pico_de_costos_en_el_anio_10(self):
        costos = {f.anio: f.costos_om_cop for f in self.filas[1:]}
        self.assertEqual(max(costos, key=costos.get), FINANZAS.anio_reemplazo_baterias)

    def test_tir_entre_14_y_15_por_ciento(self):
        self.assertGreaterEqual(self.kpis.tir_porcentaje, 14.0)
        self.assertLessEqual(self.kpis.tir_porcentaje, 15.0)

    def test_vpn_positivo_a_la_tasa_de_descuento(self):
        self.assertGreater(self.kpis.vpn_cop, 0)

    def test_lcoe_competitivo_frente_al_diesel_nivelado(self):
        self.assertLess(self.kpis.lcoe_cop_kwh, self.kpis.costo_nivelado_diesel_cop_kwh)

    def test_control_negativo_un_capex_alto_saca_la_tir_del_rango(self):
        caro = replace(FINANZAS, capex_cop=FINANZAS.capex_cop * 2)
        kpis = c.indicadores(caro, c.flujo_de_caja(caro))
        self.assertLess(kpis.tir_porcentaje, 14.0)
