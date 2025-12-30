# api_service/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_monitoreo, name='api_dashboard'),
    # path('stats/', views.estadisticas_api, name='api_stats'),
    # path('logs/', views.ver_logs, name='api_logs'),
]