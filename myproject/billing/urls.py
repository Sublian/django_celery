# myproject\billing\urls.py

from django.urls import path
from .views.partners import (
    PartnerListView,
    PartnerCreateView,
    PartnerUpdateView,
    PartnerDetailView,
    PartnerDeleteView,
)

from .views.company import (
    company_list,
    company_create,
    company_edit,
    company_detail,
    company_toggle_active,
)

app_name = "billing"

urlpatterns = [
    path("partners/", PartnerListView.as_view(), name="partner_list"),
    path("partners/new/", PartnerCreateView.as_view(), name="partner_create"),
    path("partners/<int:pk>/edit/", PartnerUpdateView.as_view(), name="partner_update"),
    path("partners/<int:pk>/", PartnerDetailView.as_view(), name="partner_detail"),
    path("partners/<int:pk>/delete/", PartnerDeleteView.as_view(), name="partner_delete"),
    
    path('company/', company_list, name='company_list'),
    path('company/create/', company_create, name='company_create'),
    path('company/<int:pk>/', company_detail, name='company_detail'),
    path('company/<int:pk>/edit/', company_edit, name='company_edit'),
    path('company/<int:pk>/toggle/', company_toggle_active, name='company_toggle_active'),
]
