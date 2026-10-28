from django.db import IntegrityError
from django.test import TestCase

from monitoreo.tests import crear_registro

from .models import PrediccionYAnomalia


class PrediccionYAnomaliaTests(TestCase):
    def test_related_name_analitica(self):
        registro = crear_registro()
        PrediccionYAnomalia.objects.create(
            registro=registro, generacion_predicha_kwh=33.0, demanda_predicha_kwh=12.5
        )
        registro.refresh_from_db()
        self.assertEqual(registro.analitica.generacion_predicha_kwh, 33.0)

    def test_no_es_anomalia_por_defecto(self):
        prediccion = PrediccionYAnomalia.objects.create(
            registro=crear_registro(), generacion_predicha_kwh=1.0, demanda_predicha_kwh=1.0
        )
        self.assertFalse(prediccion.es_anomalia)
        self.assertIsNone(prediccion.tipo_anomalia)
        self.assertIsNone(prediccion.descripcion_anomalia)

    def test_una_sola_prediccion_por_registro(self):
        registro = crear_registro()
        PrediccionYAnomalia.objects.create(
            registro=registro, generacion_predicha_kwh=1.0, demanda_predicha_kwh=1.0
        )
        with self.assertRaises(IntegrityError):
            PrediccionYAnomalia.objects.create(
                registro=registro, generacion_predicha_kwh=2.0, demanda_predicha_kwh=2.0
            )

    def test_borrar_registro_borra_su_prediccion(self):
        registro = crear_registro()
        PrediccionYAnomalia.objects.create(
            registro=registro, generacion_predicha_kwh=1.0, demanda_predicha_kwh=1.0
        )
        registro.delete()
        self.assertFalse(PrediccionYAnomalia.objects.exists())
