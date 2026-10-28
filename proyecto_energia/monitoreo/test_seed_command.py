"""El comando seed_amalfi_data contra la base: conteos, idempotencia y coherencia guardada."""

from io import StringIO

from django.core.management import CommandError, call_command
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from analitica import services as analitica
from analitica.models import PrediccionYAnomalia
from financiero import calculos
from financiero.models import FlujoCajaAnual, ResumenFinanciero
from monitoreo.management.commands import seed_amalfi_data as seed
from monitoreo.models import ConsumoPorSegmento, RegistroSistema
from monitoreo.services import balance_residual

ESTADOS = RegistroSistema.EstadoSistema.values

TOLERANCIA_ENERGIA_ANUAL = 0.15


def sembrar(**opciones):
    call_command("seed_amalfi_data", stdout=StringIO(), **opciones)


class SeedComandoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sembrar()

    def test_conteos(self):
        self.assertEqual(RegistroSistema.objects.count(), 720)
        self.assertEqual(ConsumoPorSegmento.objects.count(), 720 * 4)
        self.assertEqual(PrediccionYAnomalia.objects.count(), 720)
        self.assertEqual(ResumenFinanciero.objects.count(), 1)
        self.assertEqual(FlujoCajaAnual.objects.count(), 26)

    def test_idempotente(self):
        sembrar()
        self.assertEqual(RegistroSistema.objects.count(), 720)
        self.assertEqual(ConsumoPorSegmento.objects.count(), 720 * 4)
        self.assertEqual(ResumenFinanciero.objects.count(), 1)
        self.assertEqual(FlujoCajaAnual.objects.count(), 26)

    def test_demanda_total_es_la_suma_de_segmentos_guardados(self):
        sumas = dict(
            ConsumoPorSegmento.objects.values("registro")
            .annotate(total=Sum("consumo_kwh"))
            .values_list("registro", "total")
        )
        for r in RegistroSistema.objects.only("id", "demanda_total_kwh"):
            self.assertAlmostEqual(r.demanda_total_kwh, sumas[r.id], delta=1e-9)

    def test_anomalias_guardadas_con_tipo_y_descripcion(self):
        anomalias = PrediccionYAnomalia.objects.filter(es_anomalia=True)
        self.assertIn(
            anomalias.count(), range(analitica.ANOMALIAS_MIN, analitica.ANOMALIAS_MAX + 1)
        )
        for a in anomalias:
            self.assertTrue(a.tipo_anomalia)
            self.assertIn("kWh", a.descripcion_anomalia)
        normales = PrediccionYAnomalia.objects.filter(es_anomalia=False)
        self.assertFalse(normales.exclude(tipo_anomalia=None).exists())

    def test_tir_guardada_sale_del_flujo_guardado(self):
        netos = list(FlujoCajaAnual.objects.values_list("flujo_neto_cop", flat=True))
        resumen = ResumenFinanciero.actual()
        self.assertAlmostEqual(calculos.tir(netos) * 100, resumen.tir_porcentaje, delta=0.01)
        self.assertAlmostEqual(calculos.vpn(netos, seed.TASA_DESCUENTO), resumen.vpn_cop, delta=1)

    def test_energia_anual_supuesta_cuadra_con_el_mes_simulado(self):
        """La constante ENERGIA_ANUAL_SERVIDA_KWH no puede alejarse de lo que simula la planta."""
        primero = RegistroSistema.objects.first()
        # La base devuelve UTC; los perfiles horarios necesitan la hora local.
        inicio = timezone.localtime(primero.timestamp)
        escenario = seed.simulacion.generar_escenario(
            inicio, 720, seed.SEMILLA_POR_DEFECTO, seed.PLANTA
        )
        # Es el mismo escenario que se sembró, no otro desplazado.
        self.assertEqual(escenario.horas[0].generacion_fv_kwh, primero.generacion_fv_kwh)
        self.assertEqual(escenario.horas[0].demanda_total_kwh, primero.demanda_total_kwh)
        servida = sum(h.demanda_total_kwh - h.energia_no_suministrada_kwh for h in escenario.horas)
        anualizada = servida * 365 / 30
        desvio = abs(anualizada / seed.ENERGIA_ANUAL_SERVIDA_KWH - 1)
        self.assertLess(desvio, TOLERANCIA_ENERGIA_ANUAL)

    def test_ventana_por_defecto_es_la_del_documento_escrito(self):
        primera = timezone.localtime(RegistroSistema.objects.first().timestamp)
        ultima = timezone.localtime(RegistroSistema.objects.last().timestamp)
        self.assertEqual(primera.isoformat(), "2026-09-28T15:00:00-05:00")
        self.assertEqual(ultima.isoformat(), "2026-10-28T14:00:00-05:00")

    def test_sin_argumentos_reproduce_las_cifras_de_la_bitacora(self):
        """Las cifras de OT-0004 §9 (y del documento escrito). Si un supuesto de la cabecera
        cambia a propósito, esta prueba avisa que el documento también debe cambiar."""
        registros = list(RegistroSistema.objects.all())
        estados = {e: sum(r.estado_sistema == e for r in registros) for e in ESTADOS}
        self.assertEqual(estados, {"OPTIMO": 546, "ALERTA": 94, "CRITICO": 80})
        residuos = [balance_residual(r) for r in registros]
        cifras = {
            "generacion": sum(r.generacion_fv_kwh for r in registros),
            "demanda": sum(r.demanda_total_kwh for r in registros),
            "vertimiento": sum(x for x in residuos if x > 0),
            "no_suministrada": sum(-x for x in residuos if x < 0),
        }
        esperadas = {
            "generacion": 6324,
            "demanda": 4855,
            "vertimiento": 1521,
            "no_suministrada": 216,
        }
        self.assertEqual({k: round(v) for k, v in cifras.items()}, esperadas)
        segmentos = dict(
            ConsumoPorSegmento.objects.values_list("tipo_usuario").annotate(
                total=Sum("consumo_kwh")
            )
        )
        self.assertEqual(
            {k: round(v) for k, v in segmentos.items()},
            {"RESIDENCIAL": 2165, "PRODUCTIVO": 1462, "COMUNITARIO": 689, "ALUMBRADO": 540},
        )
        self.assertEqual(PrediccionYAnomalia.objects.filter(es_anomalia=True).count(), 8)
        resumen = ResumenFinanciero.actual()
        self.assertEqual(resumen.tir_porcentaje, 14.49)
        self.assertEqual(resumen.vpn_cop, 227_919_781)
        self.assertEqual(round(resumen.lcoe_cop_kwh, 2), 3173.35)


class SeedValidacionTests(TestCase):
    def test_pocos_dias_es_error(self):
        with self.assertRaises(CommandError):
            sembrar(dias=seed.DIAS_MINIMOS - 1)
        self.assertFalse(RegistroSistema.objects.exists())

    def test_hasta_desplaza_la_ventana(self):
        sembrar(dias=seed.DIAS_MINIMOS, hasta="2026-10-01T10:00")
        ultima = timezone.localtime(RegistroSistema.objects.last().timestamp)
        self.assertEqual(ultima.isoformat(), "2026-10-01T10:00:00-05:00")

    def test_hasta_con_zona_se_convierte_y_se_trunca_a_la_hora(self):
        sembrar(dias=seed.DIAS_MINIMOS, hasta="2026-10-01T15:42+00:00")
        ultima = timezone.localtime(RegistroSistema.objects.last().timestamp)
        self.assertEqual(ultima.isoformat(), "2026-10-01T10:00:00-05:00")

    def test_hasta_invalido_es_error_y_no_borra_nada(self):
        sembrar(dias=seed.DIAS_MINIMOS)
        for valor in (
            "ayer",
            "2026-10-01",
            "20261001T1000",
            "2026-W40-1T10:00",
            "2026-02-30T10:00",
            "0001-01-01T00:00",  # la ventana de 30 días caería antes del año 1
        ):
            with self.subTest(hasta=valor), self.assertRaises(CommandError):
                sembrar(hasta=valor)
        self.assertEqual(RegistroSistema.objects.count(), seed.DIAS_MINIMOS * 24)

    def test_dias_minimos_funciona(self):
        sembrar(dias=seed.DIAS_MINIMOS)
        self.assertEqual(RegistroSistema.objects.count(), seed.DIAS_MINIMOS * 24)
