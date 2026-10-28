"""Vista HTML del dashboard (OT-0006). El comportamiento en el navegador se verifica en OT-0007."""

import json
import re
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from monitoreo.views import PESTANAS

# Librería vendorizada con su versión exacta en la ruta: «vendor/chartjs/4.4.7/…».
VERSION_EN_RUTA = re.compile(r"/\d+\.\d+\.\d+/")


class DashboardHtmlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.html = cls.client_class().get(reverse("monitoreo:dashboard")).content.decode()

    def test_seis_pestanas_con_su_panel(self):
        self.assertEqual(len(PESTANAS), 6)
        for id_, titulo, _icono in PESTANAS:
            with self.subTest(pestana=id_):
                self.assertIn(f'id="panel-{id_}"', self.html)
                self.assertIn(f'aria-controls="panel-{id_}"', self.html)
                self.assertIn(titulo, self.html)

    def test_ninguna_url_externa_funciona_sin_internet(self):
        """OT-0008: en una ZNI no hay internet garantizado; todo se sirve desde /static/."""
        externas = re.findall(r'(?:src|href)="((?:https?:)?//[^"]+)"', self.html)
        externas += re.findall(r"url\(\s*['\"]?((?:https?:)?//[^)'\"]+)", self.html)
        self.assertEqual(externas, [])

    def test_librerias_locales_del_manifiesto(self):
        locales = re.findall(r'(?:src|href)="/static/vendor/([^"]+)"', self.html)
        self.assertEqual(len(locales), 5)  # Inter, Tailwind, Chart.js, Lucide, Alpine
        manifiesto = json.loads(Path(finders.find("vendor/MANIFIESTO.json")).read_text())
        for ruta in locales:
            with self.subTest(ruta=ruta):
                self.assertIn(ruta, manifiesto["archivos"])
                self.assertRegex(ruta, VERSION_EN_RUTA)

    def test_ningun_comentario_de_plantilla_se_imprime(self):
        """{# … #} de varias líneas no es comentario en Django: se imprime en la página."""
        self.assertNotIn("{#", self.html)
        self.assertNotIn("#}", self.html)

    def test_rotulo_de_datos_sinteticos(self):
        self.assertIn("Datos sintéticos", self.html)

    def test_url_de_la_api_viene_del_router(self):
        self.assertIn(reverse("monitoreo:api_dashboard_data"), self.html)


class DashboardJsTests(TestCase):
    def test_cada_pestana_tiene_sus_graficos_en_el_js(self):
        """Las pestañas se definen en Python (views.PESTANAS) y los gráficos en JS: no pueden
        desincronizarse, y cada canvas del HTML debe tener su constructor."""
        js = open(finders.find("monitoreo/dashboard.js"), encoding="utf-8").read()
        bloque = re.search(r"const GRAFICOS_POR_PESTANA = \{(.*?)\};", js, re.S).group(1)
        pestanas_js = set(re.findall(r"^\s*(\w+):", bloque, re.M))
        self.assertEqual(pestanas_js, {id_ for id_, _t, _i in PESTANAS})

        html = self.client.get(reverse("monitoreo:dashboard")).content.decode()
        lienzos = set(re.findall(r'<canvas id="([\w-]+)"', html))
        en_pestanas = set(re.findall(r'"(g-[\w-]+)"', bloque))
        constructores = set(re.findall(r'^\s*"(g-[\w-]+)": \(p\)', js, re.M))
        self.assertEqual(lienzos, en_pestanas)
        self.assertEqual(lienzos, constructores)
