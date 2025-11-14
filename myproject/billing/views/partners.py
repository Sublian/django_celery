from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from billing.models import Partner


class PartnerListView(ListView):
    model = Partner
    template_name = "billing/partners/list.html"
    context_object_name = "partners"


class PartnerCreateView(CreateView):
    model = Partner
    template_name = "billing/partners/form.html"
    fields = "__all__"
    success_url = reverse_lazy("partner_list")


class PartnerUpdateView(UpdateView):
    model = Partner
    template_name = "billing/partners/form.html"
    fields = "__all__"
    success_url = reverse_lazy("partner_list")


class PartnerDetailView(DetailView):
    model = Partner
    template_name = "billing/partners/detail.html"
    context_object_name = "partner"


class PartnerDeleteView(UpdateView):
    """Soft Delete → No elimina, solo desactiva"""
    model = Partner
    fields = []  # No hay formulario
    template_name = "billing/partners/delete.html"
    success_url = reverse_lazy("partner_list")

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.is_active = False
        obj.save()
        return redirect(self.success_url)
