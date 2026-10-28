from django.contrib import admin

from .models import ConsumoPorSegmento, RegistroSistema


class ConsumoPorSegmentoInline(admin.TabularInline):
    model = ConsumoPorSegmento
    extra = 0


@admin.register(RegistroSistema)
class RegistroSistemaAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "irradiancia_wm2",
        "generacion_fv_kwh",
        "demanda_total_kwh",
        "soc_porcentaje",
        "estado_sistema",
    )
    list_filter = ("estado_sistema",)
    date_hierarchy = "timestamp"
    inlines = [ConsumoPorSegmentoInline]


@admin.register(ConsumoPorSegmento)
class ConsumoPorSegmentoAdmin(admin.ModelAdmin):
    list_display = ("registro", "tipo_usuario", "consumo_kwh")
    ordering = ("-registro__timestamp", "tipo_usuario")
    list_filter = ("tipo_usuario",)
    list_select_related = ("registro",)
