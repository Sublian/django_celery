from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_file, name='upload_file'),
    path('', views.dashboard, name='dashboard'),
    path('logs/', views.view_logs, name='view_logs'),
]
