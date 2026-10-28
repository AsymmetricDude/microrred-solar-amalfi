"""Verifica el dashboard en un navegador real (OT-0007).

Recorre las 6 pestañas × 3 rangos con clics reales en Chromium sin cabeza, en escritorio y en
móvil, y termina con código 1 si aparece cualquiera de estos:

- `console.error` o `console.warning`, `pageerror`, petición fallida o respuesta HTTP ≥ 400;
- menos de 6 pestañas o de 3 rangos (CLAUDE.md: 6 módulos; 24 h, 7 y 30 días);
- un gráfico visible sin valores, o con un número de puntos distinto al del rango;
- un valor vacío en pantalla («—», «NaN», «undefined») o restos de plantilla sin renderizar
  («{#», «#}», «{{», «{%») en cualquier parte del texto visible;
- scroll horizontal de la página;
- con `--offline`, cualquier petición a un host que no sea el servidor local (se bloquea: así se
  comprueba que el dashboard funciona sin internet, como en una ZNI).

Única excepción: el aviso del Play CDN de Tailwind, aceptado por el lead (2026-10-28). Se filtra
por su texto exacto, no por nivel, para que cualquier otro aviso sí cuente.

    uv run python scripts/verificar_consola.py                     # levanta su propio servidor
    uv run python scripts/verificar_consola.py --url http://127.0.0.1:8000/
    uv run python scripts/verificar_consola.py --capturas /tmp/capturas
    uv run python scripts/verificar_consola.py --offline           # sin internet (OT-0008)
    uv run python scripts/verificar_consola.py --control-negativo  # debe FALLAR

Se corre desde la raíz del repositorio.

Requiere la base sembrada (`manage.py seed_amalfi_data`) y Chromium de Playwright
(`uv run playwright install chromium`). Si faltan librerías del sistema y no hay `sudo`, ver
el README («Chromium sin sudo»).
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
DIR_DJANGO = RAIZ / "proyecto_energia"
LIBRERIAS_SIN_SUDO = Path.home() / ".cache/sun-ia-chromium-deps/root/usr/lib/x86_64-linux-gnu"
AVISO_ACEPTADO = "cdn.tailwindcss.com should not be used in production"
VENTANAS = {"escritorio": (1440, 900), "movil": (390, 844)}
# Gráficos cuyo número de puntos no depende del rango: flujo (26 años) y dona (4 segmentos).
GRAFICOS_SIN_RANGO = {"g-flujo", "g-participacion"}
PESTANAS_ESPERADAS = 6
RANGOS_ESPERADOS = 3
VALORES_VACIOS = ("—", "NaN", "undefined")
# Un {# … #} de varias líneas se imprime como texto (OT-0008, fuera de los paneles).
RESTOS_DE_PLANTILLA = ("{#", "#}", "{{", "{%")
HOSTS_LOCALES = {"127.0.0.1", "localhost"}
ESPERA_SERVIDOR_S = 30
TIEMPO_MAXIMO_MS = 15_000


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def servidor_propio():
    """`runserver` en un puerto libre mientras dura la verificación."""
    puerto = puerto_libre()
    url = f"http://127.0.0.1:{puerto}/"
    proceso = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{puerto}", "--noreload"],
        cwd=DIR_DJANGO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        limite = time.monotonic() + ESPERA_SERVIDOR_S
        while True:
            try:
                urllib.request.urlopen(url, timeout=2)
                break
            except OSError:
                if time.monotonic() > limite or proceso.poll() is not None:
                    raise SystemExit(
                        f"El servidor no respondió en {ESPERA_SERVIDOR_S} s."
                    ) from None
                time.sleep(0.3)
        yield url
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.wait()


def entorno_chromium() -> dict:
    """Si existen las librerías extraídas sin sudo, Chromium las encuentra por LD_LIBRARY_PATH."""
    entorno = dict(os.environ)
    if LIBRERIAS_SIN_SUDO.is_dir():
        previas = entorno.get("LD_LIBRARY_PATH", "")
        entorno["LD_LIBRARY_PATH"] = f"{LIBRERIAS_SIN_SUDO}:{previas}".rstrip(":")
    return entorno


def comprobar_datos(url: str) -> None:
    with urllib.request.urlopen(f"{url}api/dashboard-data/?dias=1", timeout=10) as respuesta:
        if json.load(respuesta)["sin_datos"]:
            raise SystemExit("La base está vacía: ejecuta `manage.py seed_amalfi_data` antes.")


# Por gráfico: puntos del eje X y cuántos valores numéricos distintos de cero tiene. Un gráfico
# con etiquetas pero sin valores se dibuja plano: contar etiquetas no basta.
GRAFICOS_VISIBLES_JS = """() => [...document.querySelectorAll('canvas')]
  .filter((c) => c.offsetParent !== null)
  .map((c) => {
    const g = Chart.getChart(c);
    if (!g) return { id: c.id, puntos: null, valores: 0 };
    const valores = g.data.datasets
      .flatMap((ds) => ds.data)
      .filter((v) => typeof v === 'number' && Number.isFinite(v) && v !== 0).length;
    return { id: c.id, puntos: g.data.labels.length, valores };
  })"""
TEXTO_PANEL_JS = "(id) => document.getElementById(`panel-${id}`).innerText"
ESTADO = "document.querySelector('[x-data]')._x_dataStack[0]"
# El clic cambia `dias` al instante; los datos llegan después. Se espera a que el rango cargado
# sea el pedido (networkidle no basta: Alpine guarda la respuesta tras leer el JSON).
RANGO_CARGADO_JS = (
    f"() => {{ const s = {ESTADO}; return !s.cargando && s.d && s.d.rango.dias === s.dias; }}"
)
REGISTROS_JS = f"() => {ESTADO}.d.rango.n_registros"
SCROLL_JS = "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"


def vaciar_respuesta(ruta):
    respuesta = ruta.fetch()
    datos = respuesta.json()
    datos["kpis"] = dict.fromkeys(datos["kpis"])
    datos["series"] = {
        clave: valores if clave == "timestamps" else [None] * len(valores)
        for clave, valores in datos["series"].items()
    }
    ruta.fulfill(response=respuesta, json=datos)


def recorrer(
    navegador,
    url: str,
    nombre: str,
    tamano,
    capturas: Path | None,
    control: bool,
    offline: bool = False,
):
    """Devuelve la lista de problemas encontrados en una ventana."""
    problemas = []
    bloqueadas = set()
    pagina = navegador.new_page(viewport={"width": tamano[0], "height": tamano[1]})
    pagina.set_default_timeout(TIEMPO_MAXIMO_MS)

    def en_consola(mensaje):
        if mensaje.type in ("error", "warning") and AVISO_ACEPTADO not in mensaje.text:
            problemas.append(f"console.{mensaje.type}: {mensaje.text}")

    pagina.on("console", en_consola)
    pagina.on("pageerror", lambda e: problemas.append(f"pageerror: {e}"))
    pagina.on(
        "requestfailed",
        lambda r: (
            r.url not in bloqueadas and problemas.append(f"requestfailed: {r.url} {r.failure}")
        ),
    )

    if offline:
        # Se registra antes que la ruta del control negativo: Playwright prueba las rutas de la
        # última a la primera, así que la de la API (local) sigue funcionando.
        def sin_internet(ruta):
            if urlparse(ruta.request.url).hostname in HOSTS_LOCALES | {urlparse(url).hostname}:
                ruta.continue_()
                return
            bloqueadas.add(ruta.request.url)
            problemas.append(f"petición externa bloqueada: {ruta.request.url}")
            ruta.abort("internetdisconnected")

        pagina.route("**/*", sin_internet)
    pagina.on(
        "response",
        lambda r: r.status >= 400 and problemas.append(f"HTTP {r.status}: {r.url}"),
    )
    if control:
        # Control negativo: un error de JS, un aviso de consola y un 404 a propósito, uno por
        # canal vigilado. Si el script no falla con los tres, no mide lo que dice.
        pagina.add_init_script(
            "addEventListener('load', () => setTimeout(() => {"
            " console.warn('control negativo: aviso');"
            " fetch('/no-existe-control-negativo');"
            " throw new Error('control negativo: error'); }));"
        )
        if offline:
            # Sin internet, una petición externa también tiene que aparecer.
            pagina.add_init_script(
                "addEventListener('load', () => fetch('https://example.com/control-negativo')"
                ".catch(() => {}));"
            )
        # …y la API devuelve los KPIs y las series vacíos: el dashboard «carga» pero no muestra
        # nada. Debe aparecer como «sin valores» y «valor vacío».
        pagina.route("**/api/dashboard-data/**", vaciar_respuesta)

    pagina.goto(url, wait_until="networkidle")
    texto_pagina = pagina.evaluate("() => document.body.innerText")
    for resto in RESTOS_DE_PLANTILLA:
        if resto in texto_pagina:
            problemas.append(f"resto de plantilla «{resto}» visible en la página")
    pestanas = pagina.locator("[role=tab][data-pestana]").locator("visible=true")
    ids = [pestanas.nth(i).get_attribute("data-pestana") for i in range(pestanas.count())]
    rangos = pagina.get_by_role("group", name="Rango de fechas").get_by_role("button")
    if len(ids) != PESTANAS_ESPERADAS:
        problemas.append(f"{len(ids)} pestañas visibles, se esperaban {PESTANAS_ESPERADAS}")
    if rangos.count() != RANGOS_ESPERADOS:
        problemas.append(f"{rangos.count()} rangos, se esperaban {RANGOS_ESPERADOS}")

    for r in range(rangos.count()):
        boton = rangos.nth(r)
        texto_rango = boton.inner_text()
        boton.click()
        pagina.wait_for_function(RANGO_CARGADO_JS)
        registros = pagina.evaluate(REGISTROS_JS)
        for id_pestana in ids:
            pagina.locator(f"[role=tab][data-pestana='{id_pestana}']").locator(
                "visible=true"
            ).click()
            pagina.wait_for_timeout(150)
            for grafico in pagina.evaluate(GRAFICOS_VISIBLES_JS):
                if grafico["puntos"] is None:
                    problemas.append(f"{texto_rango}/{id_pestana}: {grafico['id']} sin gráfico")
                elif grafico["valores"] == 0:
                    problemas.append(f"{texto_rango}/{id_pestana}: {grafico['id']} sin valores")
                elif grafico["id"] not in GRAFICOS_SIN_RANGO and grafico["puntos"] != registros:
                    problemas.append(
                        f"{texto_rango}/{id_pestana}: {grafico['id']} con {grafico['puntos']} "
                        f"puntos, se esperaban {registros}"
                    )
            texto = pagina.evaluate(TEXTO_PANEL_JS, id_pestana)
            for vacio in VALORES_VACIOS:
                if vacio in texto:
                    problemas.append(f"{texto_rango}/{id_pestana}: valor vacío «{vacio}»")
            if pagina.evaluate(SCROLL_JS):
                problemas.append(f"{texto_rango}/{id_pestana}: scroll horizontal")
            if capturas:
                archivo = capturas / f"{nombre}-{texto_rango.replace(' ', '')}-{id_pestana}.png"
                pagina.screenshot(path=archivo, full_page=True)
    print(f"  {nombre}: {rangos.count()} rangos × {len(ids)} pestañas recorridos")
    pagina.close()
    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="Dashboard ya levantado; si se omite, se levanta uno.")
    parser.add_argument("--capturas", type=Path, help="Carpeta donde guardar capturas.")
    parser.add_argument("--control-negativo", action="store_true", help="Inyecta un error de JS.")
    parser.add_argument(
        "--offline", action="store_true", help="Bloquea toda petición que no sea al servidor local."
    )
    args = parser.parse_args()
    if args.capturas:
        args.capturas.mkdir(parents=True, exist_ok=True)

    with servidor_propio() if not args.url else _ya_levantado(args.url) as url:
        comprobar_datos(url)
        print(
            f"Verificando {url}"
            + (" sin internet (peticiones externas bloqueadas)" if args.offline else "")
        )
        problemas = []
        with sync_playwright() as p:
            navegador = p.chromium.launch(env=entorno_chromium())
            for nombre, tamano in VENTANAS.items():
                problemas += recorrer(
                    navegador,
                    url,
                    nombre,
                    tamano,
                    args.capturas,
                    args.control_negativo,
                    args.offline,
                )
            navegador.close()

    if problemas:
        print(f"FALLA: {len(problemas)} problema(s)")
        for problema in problemas:
            print(f"  - {problema}")
        return 1
    print("OK: sin errores de consola, peticiones fallidas ni gráficos vacíos.")
    return 0


@contextmanager
def _ya_levantado(url: str):
    yield url if url.endswith("/") else f"{url}/"


if __name__ == "__main__":
    sys.exit(main())
