from django.contrib import admin

from .models import PrediccionYAnomalia


@admin.register(PrediccionYAnomalia)
class PrediccionYAnomaliaAdmin(admin.ModelAdmin):
    list_display = (
        "registro",
        "generacion_predicha_kwh",
        "demanda_predicha_kwh",
        "es_anomalia",
        "tipo_anomalia",
    )
    list_filter = ("es_anomalia", "tipo_anomalia")
    ordering = ("-registro__timestamp",)
    list_select_related = ("registro",)
