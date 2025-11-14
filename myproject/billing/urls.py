from django.urls import path
from .views.partners import (
    PartnerListView,
    PartnerCreateView,
    PartnerUpdateView,
    PartnerDetailView,
    PartnerDeleteView,
)

urlpatterns = [
    path("partners/", PartnerListView.as_view(), name="partner_list"),
    path("partners/new/", PartnerCreateView.as_view(), name="partner_create"),
    path("partners/<int:pk>/edit/", PartnerUpdateView.as_view(), name="partner_update"),
    path("partners/<int:pk>/", PartnerDetailView.as_view(), name="partner_detail"),
    path("partners/<int:pk>/delete/", PartnerDeleteView.as_view(), name="partner_delete"),
    
]
