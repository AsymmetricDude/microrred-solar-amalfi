from django.db import models

from monitoreo.models import RegistroSistema


class PrediccionYAnomalia(models.Model):
    """Predicción (mock, ver ADR-0001) y resultado de la detección de anomalías por hora."""

    registro = models.OneToOneField(
        RegistroSistema,
        on_delete=models.CASCADE,
        related_name="analitica",
        verbose_name="registro",
    )
    generacion_predicha_kwh = models.FloatField("generación predicha (kWh)")
    demanda_predicha_kwh = models.FloatField("demanda predicha (kWh)")
    # Indexado: la API lista las anomalías del rango filtrando por este campo.
    es_anomalia = models.BooleanField("es anomalía", default=False, db_index=True)
    # null=True va contra la convención de Django (DJ001), pero CLAUDE.md §4 lo especifica así:
    # una hora sin anomalía guarda NULL, no cadena vacía.
    tipo_anomalia = models.CharField(  # noqa: DJ001
        "tipo de anomalía", max_length=40, blank=True, null=True
    )
    descripcion_anomalia = models.TextField(  # noqa: DJ001
        "descripción de la anomalía", blank=True, null=True
    )

    class Meta:
        # Sin `ordering` por defecto, para no forzar un JOIN con RegistroSistema en cada consulta.
        verbose_name = "predicción y anomalía"
        verbose_name_plural = "predicciones y anomalías"

    def __str__(self):
        if self.registro_id is None:
            return "Predicción sin registro"
        marca = f" · {self.tipo_anomalia}" if self.es_anomalia else ""
        return f"Predicción {self.registro}{marca}"
