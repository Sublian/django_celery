from django.urls import path, include
from . import views

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('', views.dashboard, name='dashboard'),
    path('logs/', views.view_logs, name='view_logs'),
    path('pending/', views.pending_tasks_monitor, name='pending_tasks_monitor'),
    path('pending/reprocesar/', views.reprocesar_pendientes, name='reprocesar_pendientes'),
    path('api/', include('api_service.urls')), 

]
