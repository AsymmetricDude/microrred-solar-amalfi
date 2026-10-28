from django.conf import settings
from django.test import SimpleTestCase


class ConfiguracionRegionalTests(SimpleTestCase):
    def test_idioma_y_zona_horaria_de_colombia(self):
        self.assertEqual(settings.LANGUAGE_CODE, "es-co")
        self.assertEqual(settings.TIME_ZONE, "America/Bogota")
        self.assertTrue(settings.USE_TZ)
