from django.apps import apps
from django.test import SimpleTestCase


class AppInstaladaTests(SimpleTestCase):
    def test_app_registrada(self):
        self.assertTrue(apps.is_installed("analitica"))
