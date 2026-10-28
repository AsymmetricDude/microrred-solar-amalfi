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

TOLERANCIA_ENERGIA_ANUAL = 0.15


def sembrar(**opciones):
    call_command("seed_amalfi_data", stdout=StringIO(), **opciones)


class SeedComandoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # La ventana se calcula con la hora actual: se mide antes y después de sembrar por si la
        # prueba cruza un cambio de hora.
        cls.inicios_posibles = {seed.inicio_de_ventana(30)}
        sembrar()
        cls.inicios_posibles.add(seed.inicio_de_ventana(30))

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

    def test_ventana_termina_en_la_ultima_hora_completa(self):
        primera = RegistroSistema.objects.first().timestamp
        ultima = RegistroSistema.objects.last().timestamp
        self.assertIn(primera, self.inicios_posibles)
        self.assertEqual(ultima - primera, seed.timedelta(hours=719))


class SeedValidacionTests(TestCase):
    def test_pocos_dias_es_error(self):
        with self.assertRaises(CommandError):
            sembrar(dias=seed.DIAS_MINIMOS - 1)
        self.assertFalse(RegistroSistema.objects.exists())

    def test_dias_minimos_funciona(self):
        sembrar(dias=seed.DIAS_MINIMOS)
        self.assertEqual(RegistroSistema.objects.count(), seed.DIAS_MINIMOS * 24)
