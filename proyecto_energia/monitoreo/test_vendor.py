"""Librerías vendorizadas (OT-0008): lo servido es exactamente lo descargado de su origen."""

import hashlib
import json
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

MANIFIESTO = Path(finders.find("vendor/MANIFIESTO.json"))
VENDOR = MANIFIESTO.parent


class VendorTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.archivos = json.loads(MANIFIESTO.read_text())["archivos"]

    def test_sha256_de_cada_archivo(self):
        for ruta, datos in self.archivos.items():
            with self.subTest(ruta=ruta):
                digest = hashlib.sha256((VENDOR / ruta).read_bytes()).hexdigest()
                self.assertEqual(digest, datos["sha256"])

    def test_cada_archivo_con_su_licencia(self):
        for ruta, datos in self.archivos.items():
            with self.subTest(ruta=ruta):
                self.assertTrue((VENDOR / datos["texto_licencia"]).is_file())

    def test_nada_sin_declarar_en_vendor(self):
        """Un archivo en vendor/ que no está en el manifiesto no tiene origen ni licencia."""
        presentes = {
            str(p.relative_to(VENDOR))
            for p in VENDOR.rglob("*")
            if p.is_file() and p.parent.name != "licencias" and p.name != "MANIFIESTO.json"
        }
        self.assertEqual(presentes, set(self.archivos))
