from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import IntegrityError
from django.test import TestCase

from analitica.models import PrediccionYAnomalia
from financiero.models import FlujoCajaAnual, ResumenFinanciero

from .models import ConsumoPorSegmento, RegistroSistema

BOGOTA = ZoneInfo("America/Bogota")


def crear_registro(hora=12, **campos):
    valores = {
        "timestamp": datetime(2026, 10, 1, hora, tzinfo=BOGOTA),
        "irradiancia_wm2": 900.0,
        "temp_ambiente_c": 27.0,
        "temp_panel_c": 44.0,
        "generacion_fv_kwh": 35.0,
        "demanda_total_kwh": 12.0,
        "soc_porcentaje": 80.0,
        "autonomia_horas": 14.0,
        "potencia_bateria_kw": 20.0,
        "estado_sistema": RegistroSistema.EstadoSistema.OPTIMO,
    }
    valores.update(campos)
    return RegistroSistema.objects.create(**valores)


def esquema(modelo):
    """{campo: tipo de Django} de los campos concretos, sin la clave primaria automática."""
    return {
        f.name: f.get_internal_type() for f in modelo._meta.concrete_fields if not f.primary_key
    }


FLOAT, BIGINT = "FloatField", "BigIntegerField"


class EsquemaSegunClaudeMdTests(TestCase):
    """Nombres y tipos de CLAUDE.md §4: si alguien renombra o cambia el tipo de un campo, falla."""

    def test_campos_y_tipos_exactos_de_los_cinco_modelos(self):
        esperados = {
            RegistroSistema: {
                "timestamp": "DateTimeField",
                "irradiancia_wm2": FLOAT,
                "temp_ambiente_c": FLOAT,
                "temp_panel_c": FLOAT,
                "generacion_fv_kwh": FLOAT,
                "demanda_total_kwh": FLOAT,
                "soc_porcentaje": FLOAT,
                "autonomia_horas": FLOAT,
                "potencia_bateria_kw": FLOAT,
                "estado_sistema": "CharField",
            },
            ConsumoPorSegmento: {
                "registro": "ForeignKey",
                "tipo_usuario": "CharField",
                "consumo_kwh": FLOAT,
            },
            PrediccionYAnomalia: {
                "registro": "OneToOneField",
                "generacion_predicha_kwh": FLOAT,
                "demanda_predicha_kwh": FLOAT,
                "es_anomalia": "BooleanField",
                "tipo_anomalia": "CharField",
                "descripcion_anomalia": "TextField",
            },
            ResumenFinanciero: {
                "capex_cop": BIGINT,
                "opex_anual_cop": BIGINT,
                "vpn_cop": BIGINT,
                "tir_porcentaje": FLOAT,
                "lcoe_cop_kwh": FLOAT,
                "ahorro_anual_diesel_cop": BIGINT,
                "toneladas_co2_evitadas_anual": FLOAT,
            },
            FlujoCajaAnual: {
                "anio": "IntegerField",
                "ingresos_ahorro_cop": BIGINT,
                "costos_om_cop": BIGINT,
                "flujo_neto_cop": BIGINT,
                "flujo_acumulado_cop": BIGINT,
            },
        }
        for modelo, campos in esperados.items():
            with self.subTest(modelo=modelo.__name__):
                self.assertEqual(esquema(modelo), campos)

    def test_related_names(self):
        self.assertEqual(
            ConsumoPorSegmento._meta.get_field("registro").remote_field.related_name, "segmentos"
        )
        self.assertEqual(
            PrediccionYAnomalia._meta.get_field("registro").remote_field.related_name, "analitica"
        )

    def test_opciones_de_estado_y_tipo_de_usuario(self):
        self.assertEqual(set(RegistroSistema.EstadoSistema.values), {"OPTIMO", "ALERTA", "CRITICO"})
        self.assertEqual(
            set(ConsumoPorSegmento.TipoUsuario.values),
            {"RESIDENCIAL", "PRODUCTIVO", "COMUNITARIO", "ALUMBRADO"},
        )

    def test_timestamp_indexado(self):
        campo = RegistroSistema._meta.get_field("timestamp")
        self.assertTrue(campo.unique)
        self.assertTrue(campo.db_index)


class RegistroSistemaTests(TestCase):
    def test_timestamp_unico(self):
        crear_registro()
        with self.assertRaises(IntegrityError):
            crear_registro()

    def test_orden_cronologico(self):
        crear_registro(hora=15)
        crear_registro(hora=9)
        horas = [r.timestamp.astimezone(BOGOTA).hour for r in RegistroSistema.objects.all()]
        self.assertEqual(horas, [9, 15])


class ConsumoPorSegmentoTests(TestCase):
    def test_related_name_segmentos(self):
        registro = crear_registro()
        ConsumoPorSegmento.objects.create(
            registro=registro, tipo_usuario="RESIDENCIAL", consumo_kwh=5.0
        )
        ConsumoPorSegmento.objects.create(
            registro=registro, tipo_usuario="ALUMBRADO", consumo_kwh=1.5
        )
        self.assertEqual(registro.segmentos.count(), 2)

    def test_un_valor_por_segmento_y_hora(self):
        registro = crear_registro()
        ConsumoPorSegmento.objects.create(
            registro=registro, tipo_usuario="PRODUCTIVO", consumo_kwh=8.0
        )
        with self.assertRaises(IntegrityError):
            ConsumoPorSegmento.objects.create(
                registro=registro, tipo_usuario="PRODUCTIVO", consumo_kwh=9.0
            )

    def test_borrar_registro_borra_sus_segmentos(self):
        registro = crear_registro()
        ConsumoPorSegmento.objects.create(
            registro=registro, tipo_usuario="COMUNITARIO", consumo_kwh=3.0
        )
        registro.delete()
        self.assertFalse(ConsumoPorSegmento.objects.exists())

    def test_str_en_hora_local_de_bogota(self):
        registro = crear_registro(hora=12)
        registro.refresh_from_db()  # la base lo devuelve en UTC (17:00)
        self.assertIn("12:00", str(registro))

    def test_str_de_instancias_sin_guardar(self):
        self.assertEqual(str(RegistroSistema()), "Registro sin fecha")
        self.assertEqual(str(PrediccionYAnomalia()), "Predicción sin registro")
