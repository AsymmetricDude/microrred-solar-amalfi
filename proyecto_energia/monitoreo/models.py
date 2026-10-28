from django.db import models
from django.utils import timezone


class RegistroSistema(models.Model):
    """Estado horario de la microrred: clima, generación FV, demanda y batería."""

    class EstadoSistema(models.TextChoices):
        OPTIMO = "OPTIMO", "Óptimo"
        ALERTA = "ALERTA", "Alerta"
        CRITICO = "CRITICO", "Crítico"

    timestamp = models.DateTimeField("fecha y hora", unique=True, db_index=True)
    irradiancia_wm2 = models.FloatField("irradiancia (W/m²)")
    temp_ambiente_c = models.FloatField("temperatura ambiente (°C)")
    temp_panel_c = models.FloatField("temperatura del panel (°C)")
    generacion_fv_kwh = models.FloatField("generación FV (kWh)")
    demanda_total_kwh = models.FloatField("demanda total (kWh)")
    soc_porcentaje = models.FloatField("estado de carga (%)", help_text="0 a 100 %")
    autonomia_horas = models.FloatField("autonomía (h)")
    potencia_bateria_kw = models.FloatField(
        "potencia de batería (kW)", help_text="Positivo: carga. Negativo: descarga."
    )
    estado_sistema = models.CharField(
        "estado del sistema", max_length=10, choices=EstadoSistema.choices
    )

    class Meta:
        ordering = ["timestamp"]
        verbose_name = "registro del sistema"
        verbose_name_plural = "registros del sistema"

    def __str__(self):
        if self.timestamp is None:
            return "Registro sin fecha"
        # La base devuelve UTC; se muestra en la hora local de Amalfi (TIME_ZONE).
        return f"{timezone.localtime(self.timestamp):%Y-%m-%d %H:%M} · {self.estado_sistema}"


class ConsumoPorSegmento(models.Model):
    """Desglose horario de la demanda por tipo de usuario."""

    class TipoUsuario(models.TextChoices):
        RESIDENCIAL = "RESIDENCIAL", "Residencial"
        PRODUCTIVO = "PRODUCTIVO", "Productivo"
        COMUNITARIO = "COMUNITARIO", "Comunitario"
        ALUMBRADO = "ALUMBRADO", "Alumbrado público"

    registro = models.ForeignKey(
        RegistroSistema,
        on_delete=models.CASCADE,
        related_name="segmentos",
        verbose_name="registro",
    )
    tipo_usuario = models.CharField("tipo de usuario", max_length=12, choices=TipoUsuario.choices)
    consumo_kwh = models.FloatField("consumo (kWh)")

    class Meta:
        # Sin `ordering` por defecto: ordenar por registro__timestamp añadiría un JOIN a toda
        # consulta. Quien necesite orden cronológico lo pide explícito.
        verbose_name = "consumo por segmento"
        verbose_name_plural = "consumos por segmento"
        constraints = [
            models.UniqueConstraint(
                fields=["registro", "tipo_usuario"], name="un_consumo_por_segmento_y_hora"
            )
        ]

    def __str__(self):
        return f"{self.get_tipo_usuario_display()}: {self.consumo_kwh:.2f} kWh"
