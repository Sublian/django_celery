from django.urls import path
from . import views

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('create/', views.user_create, name='user_create'),
    path('<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('<int:user_id>/deactivate/', views.user_deactivate, name='user_deactivate'),
    path('<int:user_id>/activate/', views.user_activate, name='user_activate'),
]