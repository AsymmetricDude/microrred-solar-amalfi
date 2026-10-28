from django.db import models


class ResumenFinanciero(models.Model):
    """KPIs económicos del caso de estudio. Hay un único registro: lo garantiza el seeder."""

    capex_cop = models.BigIntegerField("CAPEX (COP)")
    opex_anual_cop = models.BigIntegerField("OPEX anual (COP)")
    vpn_cop = models.BigIntegerField("VPN (COP)")
    tir_porcentaje = models.FloatField("TIR (%)")
    lcoe_cop_kwh = models.FloatField("LCOE (COP/kWh)")
    ahorro_anual_diesel_cop = models.BigIntegerField("ahorro anual en diésel (COP)")
    toneladas_co2_evitadas_anual = models.FloatField("CO₂ evitado al año (t)")

    class Meta:
        verbose_name = "resumen financiero"
        verbose_name_plural = "resumen financiero"

    def __str__(self):
        return f"Resumen financiero · TIR {self.tir_porcentaje:.2f} %"

    @classmethod
    def actual(cls):
        """El resumen vigente, o None si aún no se ha ejecutado seed_amalfi_data."""
        return cls.objects.order_by("-pk").first()


class FlujoCajaAnual(models.Model):
    """Flujo de caja proyectado del año 0 (inversión) al 25."""

    anio = models.IntegerField("año", unique=True)
    ingresos_ahorro_cop = models.BigIntegerField("ingresos por ahorro (COP)")
    costos_om_cop = models.BigIntegerField("costos de O&M (COP)")
    flujo_neto_cop = models.BigIntegerField("flujo neto (COP)")
    flujo_acumulado_cop = models.BigIntegerField("flujo acumulado (COP)")

    class Meta:
        ordering = ["anio"]
        verbose_name = "flujo de caja anual"
        verbose_name_plural = "flujo de caja anual"

    def __str__(self):
        return f"Año {self.anio}: {self.flujo_neto_cop:,} COP"
