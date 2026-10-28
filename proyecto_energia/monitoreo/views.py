from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import services

# (id, título, ícono de Lucide). El orden es el de CLAUDE.md y el de la navegación.
PESTANAS = [
    ("resumen", "Resumen general", "layout-dashboard"),
    ("fotovoltaico", "Monitoreo fotovoltaico", "sun"),
    ("demanda", "Gestión de demanda", "users"),
    ("almacenamiento", "Almacenamiento", "battery-charging"),
    ("analitica", "Analítica e IA", "brain-circuit"),
    ("financiero", "Financiero", "landmark"),
]


@require_GET
def dashboard(request):
    return render(request, "monitoreo/dashboard.html", {"pestanas": PESTANAS})


@require_GET
def api_dashboard_data(request):
    """JSON del dashboard: `?dias=1|7|30` (por defecto 7) o `?desde=AAAA-MM-DD&hasta=AAAA-MM-DD`."""
    try:
        rango = services.resolver_rango(request.GET)
    except services.ParametrosInvalidos as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(
        services.construir_payload(rango), json_dumps_params={"ensure_ascii": False}
    )
