from django.urls import path

from . import views

app_name = "monitoreo"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/dashboard-data/", views.api_dashboard_data, name="api_dashboard_data"),
]
