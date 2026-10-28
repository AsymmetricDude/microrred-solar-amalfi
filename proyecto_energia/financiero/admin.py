from django.contrib import admin

from .models import FlujoCajaAnual, ResumenFinanciero


@admin.register(ResumenFinanciero)
class ResumenFinancieroAdmin(admin.ModelAdmin):
    list_display = ("capex_cop", "vpn_cop", "tir_porcentaje", "lcoe_cop_kwh")


@admin.register(FlujoCajaAnual)
class FlujoCajaAnualAdmin(admin.ModelAdmin):
    list_display = (
        "anio",
        "ingresos_ahorro_cop",
        "costos_om_cop",
        "flujo_neto_cop",
        "flujo_acumulado_cop",
    )
