"""Contrato de /api/dashboard-data/ (OT-0005 §4.3 y §6)."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from analitica import services as analitica
from monitoreo import services
from monitoreo.management.commands import seed_amalfi_data as seed
from monitoreo.models import RegistroSistema

URL = reverse("monitoreo:api_dashboard_data")
CLAVES_SERIES = set(services.CLAVES_SERIES)
# Consultas por petición con datos: último timestamp, registros + analítica, segmentos,
# resumen financiero y flujo de caja. Con fechas explícitas no hace falta el último timestamp.
CONSULTAS_POR_DIAS = 5
CONSULTAS_POR_FECHAS = 4


class ApiConDatosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_amalfi_data", stdout=StringIO())
        cls.ultimo = RegistroSistema.objects.last().timestamp

    def pedir(self, **parametros):
        respuesta = self.client.get(URL, parametros)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return respuesta.json()

    def test_dias_devuelve_24_168_y_720_puntos(self):
        for dias, puntos in ((1, 24), (7, 168), (30, 720)):
            with self.subTest(dias=dias):
                datos = self.pedir(dias=dias)
                self.assertEqual(datos["rango"]["n_registros"], puntos)
                self.assertEqual(set(datos["series"]), CLAVES_SERIES)
                for clave, valores in datos["series"].items():
                    self.assertEqual(len(valores), puntos, clave)
                for tipo, valores in datos["segmentos"]["series"].items():
                    self.assertEqual(len(valores), puntos, tipo)

    def test_sin_parametros_son_7_dias(self):
        self.assertEqual(self.pedir()["rango"]["n_registros"], 168)

    def test_ventana_anclada_al_ultimo_registro(self):
        datos = self.pedir(dias=1)
        self.assertEqual(datos["rango"]["hasta"], timezone.localtime(self.ultimo).isoformat())
        esperado_desde = timezone.localtime(self.ultimo - timedelta(hours=23)).isoformat()
        self.assertEqual(datos["rango"]["desde"], esperado_desde)

    def test_rango_por_fechas_en_hora_de_bogota(self):
        fecha = timezone.localtime(self.ultimo - timedelta(days=3)).date().isoformat()
        datos = self.pedir(desde=fecha, hasta=fecha)
        self.assertEqual(datos["rango"]["n_registros"], 24)
        self.assertTrue(datos["series"]["timestamps"][0].startswith(f"{fecha}T00:00"))
        self.assertTrue(datos["series"]["timestamps"][-1].startswith(f"{fecha}T23:00"))
        self.assertIsNone(datos["rango"]["dias"])

    def test_suma_de_segmentos_es_la_demanda(self):
        datos = self.pedir(dias=30)
        total = sum(datos["segmentos"]["totales_kwh"].values())
        self.assertAlmostEqual(total, datos["kpis"]["demanda_kwh"], delta=0.05)
        self.assertAlmostEqual(
            sum(datos["segmentos"]["participacion_pct"].values()), 100, delta=0.3
        )

    def test_balance_derivado_cuadra_con_la_simulacion(self):
        """Vertimiento y no suministrada salen del residuo del balance guardado; deben coincidir
        con lo que calculó la simulación al despachar la batería."""
        datos = self.pedir(dias=30)
        inicio = timezone.localtime(RegistroSistema.objects.first().timestamp)
        horas = seed.simulacion.generar_escenario(
            inicio, 720, seed.SEMILLA_POR_DEFECTO, seed.PLANTA
        ).horas
        self.assertAlmostEqual(
            datos["kpis"]["energia_no_suministrada_kwh"],
            sum(h.energia_no_suministrada_kwh for h in horas),
            delta=0.01,
        )
        self.assertAlmostEqual(
            datos["kpis"]["vertimiento_kwh"], sum(h.vertimiento_kwh for h in horas), delta=0.01
        )

    def test_ahorro_y_co2_usan_los_supuestos_del_seeder(self):
        kpis = self.pedir(dias=30)["kpis"]
        servida = kpis["energia_servida_kwh"]
        self.assertAlmostEqual(
            kpis["ahorro_cop"], servida * seed.COSTO_DIESEL_EVITADO_COP_KWH, delta=20
        )
        self.assertAlmostEqual(
            kpis["co2_evitado_t"], servida * seed.FACTOR_EMISION_KGCO2_KWH / 1000, delta=0.001
        )

    def test_kpis_actuales_son_los_del_ultimo_registro(self):
        datos = self.pedir(dias=7)
        ultimo = RegistroSistema.objects.last()
        self.assertEqual(datos["kpis"]["estado_actual"], ultimo.estado_sistema)
        self.assertAlmostEqual(datos["kpis"]["soc_actual"], ultimo.soc_porcentaje, delta=0.05)
        self.assertEqual(sum(datos["estados"].values()), 168)

    def test_servida_es_demanda_menos_no_suministrada(self):
        kpis = self.pedir(dias=30)["kpis"]
        self.assertAlmostEqual(
            kpis["energia_servida_kwh"],
            kpis["demanda_kwh"] - kpis["energia_no_suministrada_kwh"],
            delta=0.02,
        )

    def test_timestamps_en_hora_de_bogota(self):
        for marca in self.pedir(dias=1)["series"]["timestamps"]:
            self.assertTrue(marca.endswith("-05:00"), marca)

    def test_umbrales_soc_de_la_cabecera_del_seeder(self):
        self.assertEqual(
            self.pedir(dias=1)["umbrales_soc"],
            {
                "minimo": seed.SOC_MINIMO_PCT,
                "alerta": seed.UMBRAL_ALERTA_PCT,
                "optimo": seed.UMBRAL_OPTIMO_PCT,
            },
        )

    def test_anomalias_y_metricas(self):
        analitica_ = self.pedir(dias=30)["analitica"]
        self.assertIn(
            len(analitica_["anomalias"]),
            range(analitica.ANOMALIAS_MIN, analitica.ANOMALIAS_MAX + 1),
        )
        for a in analitica_["anomalias"]:
            self.assertGreater(abs(a["desviacion_pct"]), 30)
            self.assertIn(a["variable"], ("generacion", "demanda"))
        metricas = analitica_["metricas"]
        for variable in ("generacion", "demanda"):
            self.assertGreater(metricas[variable]["r2"], 0.8)
            self.assertGreater(metricas[variable]["mae"], 0)
        # Generación sólo en horas con sol: la irradiancia es > 0 de 06:00 a 17:59 todos los
        # días (el factor de nubosidad nunca es 0), así que son 12 de cada 24 con cualquier semilla.
        self.assertEqual(metricas["generacion"]["n"], 360)
        self.assertEqual(metricas["demanda"]["n"], 720)

    def test_financiero(self):
        fin = self.pedir(dias=1)["financiero"]
        self.assertEqual(len(fin["flujo"]), 26)
        self.assertEqual(fin["tasa_descuento_pct"], 12.0)
        self.assertGreater(fin["costo_nivelado_diesel_cop_kwh"], fin["resumen"]["lcoe_cop_kwh"])
        self.assertGreater(fin["payback_simple_anios"], 7)
        self.assertLess(fin["payback_simple_anios"], 8)

    def test_numero_de_consultas_no_depende_del_rango(self):
        for dias in (1, 30):
            with self.subTest(dias=dias), self.assertNumQueries(CONSULTAS_POR_DIAS):
                self.client.get(URL, {"dias": dias})
        fecha = timezone.localtime(self.ultimo).date().isoformat()
        with self.assertNumQueries(CONSULTAS_POR_FECHAS):
            self.client.get(URL, {"desde": fecha, "hasta": fecha})

    def test_fechas_fuera_de_los_datos_devuelven_sin_datos(self):
        datos = self.pedir(desde="2020-01-01", hasta="2020-01-02")
        self.assertTrue(datos["sin_datos"])
        self.assertIsNotNone(datos["financiero"])


class ApiParametrosInvalidosTests(TestCase):
    def test_parametros_invalidos_dan_400(self):
        casos = [
            {"dias": "abc"},
            {"dias": "5"},
            {"dias": "-7"},
            {"desde": "2026-10-10"},
            {"desde": "2026-10-11", "hasta": "2026-10-10"},
            {"desde": "10/10/2026", "hasta": "2026-10-11"},
            {"dias": ""},
            {"dias": "²"},  # str.isdigit() lo acepta; int() no
            {"dias": " 7"},
            {"desde": "20261010", "hasta": "2026-10-11"},  # fromisoformat lo acepta
            {"desde": "2026-W41-1", "hasta": "2026-10-11"},
            {"desde": "2026-02-30", "hasta": "2026-03-01"},
            {"desde": "2026-01-01", "hasta": "9999-12-31"},  # desborda al pasar a UTC
        ]
        for parametros in casos:
            with self.subTest(parametros=parametros):
                respuesta = self.client.get(URL, parametros)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("error", respuesta.json())

    def test_solo_get(self):
        self.assertEqual(self.client.post(URL).status_code, 405)


class ApiBaseVaciaTests(TestCase):
    def test_base_vacia_responde_sin_datos(self):
        respuesta = self.client.get(URL, {"dias": 7})
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertTrue(datos["sin_datos"])
        self.assertIsNone(datos["kpis"])
        self.assertIsNone(datos["financiero"])
        # Misma forma que con datos.
        self.assertEqual(set(datos["series"]), CLAVES_SERIES)
        self.assertIn("umbrales_soc", datos)


class VistaDashboardTests(TestCase):
    def test_portada_responde(self):
        respuesta = self.client.get(reverse("monitoreo:dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Amalfi")


class ApiParametrosTests(TestCase):
    def test_parametros_de_la_ui_salen_de_su_fuente(self):
        datos = self.client.get(URL, {"dias": 7}).json()  # también con la base vacía
        self.assertEqual(
            datos["parametros"],
            {
                "potencia_pico_kwp": seed.POTENCIA_PICO_KWP,
                "capacidad_bateria_kwh": seed.CAPACIDAD_BATERIA_KWH,
                "perdida_potencia_pct_por_c": 0.4,
                "error_prediccion_pct": [3.0, 8.0],
                "umbral_anomalia_pct": 30.0,
                "umbral_anomalia_kwh": analitica.UMBRAL_DESVIACION_ABSOLUTA_KWH,
            },
        )
