from django.db import IntegrityError
from django.test import TestCase

from .models import FlujoCajaAnual, ResumenFinanciero


def crear_resumen(capex_cop=1_150_000_000):
    return ResumenFinanciero.objects.create(
        capex_cop=capex_cop,
        opex_anual_cop=17_250_000,
        vpn_cop=228_000_000,
        tir_porcentaje=14.49,
        lcoe_cop_kwh=3173.0,
        ahorro_anual_diesel_cop=169_500_000,
        toneladas_co2_evitadas_anual=45.2,
    )


class ResumenFinancieroTests(TestCase):
    def test_actual_sin_datos_es_none(self):
        self.assertIsNone(ResumenFinanciero.actual())

    def test_actual_devuelve_el_ultimo(self):
        crear_resumen(capex_cop=1)
        ultimo = crear_resumen(capex_cop=2)
        self.assertEqual(ResumenFinanciero.actual(), ultimo)

    def test_dinero_cabe_en_entero_de_64_bits(self):
        # Un CAPEX de billones de COP no cabría en un IntegerField de 32 bits.
        resumen = crear_resumen(capex_cop=3_000_000_000_000)
        resumen.refresh_from_db()
        self.assertEqual(resumen.capex_cop, 3_000_000_000_000)


class FlujoCajaAnualTests(TestCase):
    def crear(self, anio):
        return FlujoCajaAnual.objects.create(
            anio=anio,
            ingresos_ahorro_cop=0,
            costos_om_cop=0,
            flujo_neto_cop=0,
            flujo_acumulado_cop=0,
        )

    def test_anio_unico(self):
        self.crear(0)
        with self.assertRaises(IntegrityError):
            self.crear(0)

    def test_orden_por_anio(self):
        self.crear(2)
        self.crear(0)
        self.crear(1)
        self.assertEqual(list(FlujoCajaAnual.objects.values_list("anio", flat=True)), [0, 1, 2])
