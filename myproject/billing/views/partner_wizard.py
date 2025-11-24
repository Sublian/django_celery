# myproject/billing/views/partner_wizard.py
from django.views.generic import FormView, TemplateView
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from billing.views.mixins import WizardSessionRequiredMixin

from billing.forms.partner_steps import (
    PartnerStep1Form,
    PartnerStep2Form,
    PartnerStep3Form
)
from billing.models import Partner
from users.models import User


#   PASO 1  
class PartnerWizardStep1(FormView):
    template_name = "billing/partner/wizard/step1.html"
    form_class = PartnerStep1Form

    def form_valid(self, form):
        data = form.cleaned_data.copy()

        # Convertir parent a ID
        if data.get("parent"):
            data["parent"] = data["parent"].id
            
        self.request.session["partner_step1"] = data

        # 👇 Condición: si NO es cliente, saltarse el paso 2
        if not data.get("is_customer"):
            return redirect("billing:partner_wizard_step3")

        return redirect("billing:partner_wizard_step2")

#   PASO 2  
class PartnerWizardStep2(WizardSessionRequiredMixin, FormView):
    template_name = "billing/partner/wizard/step2.html"
    form_class = PartnerStep2Form
    required_key = "partner_step1"

    def form_valid(self, form):
        data = form.cleaned_data.copy()
        self.request.session["partner_step2"] = data
        return redirect("billing:partner_wizard_step3")


#   PASO 3  
class PartnerWizardStep3(WizardSessionRequiredMixin, FormView):
    template_name = "billing/partner/wizard/step3.html"
    form_class = PartnerStep3Form
    required_key = "partner_step1"  # step2 es opcional

    def form_valid(self, form):
        data = form.cleaned_data.copy()

        # Convertir queryset de companies a lista de IDs
        if data.get("companies"):
            data["companies"] = [c.id for c in data["companies"]]

        self.request.session["partner_step3"] = data
        return redirect("billing:partner_wizard_finish")


#   FINALIZACIÓN DEL WIZARD  
class PartnerWizardFinish(WizardSessionRequiredMixin, TemplateView):
    template_name = "billing/partner/wizard/finish.html"
    required_key = "partner_step1"

    def get(self, request, *args, **kwargs):

        data1 = request.session.get("partner_step1")
        data2 = request.session.get("partner_step2")
        data3 = request.session.get("partner_step3")

        if not data1:
            messages.error(request, "El wizard está incompleto.")
            return redirect("billing:partner_wizard_step1")

        # --- Preparar relación padre
        parent_id = data1.pop("parent", None)
        if parent_id:
            data1["parent_id"] = parent_id

        # --- Crear Partner
        partner = Partner.objects.create(**data1)

        # --- Crear usuario si fue solicitado
        if data2 and data2.get("create_user"):
            # Intentar usar documento del usuario (Step2)
            doc_number = data2.get("document_number")

            # Si no viene, usar el documento del partner
            if not doc_number:
                doc_number = partner.num_document

            user = User.objects.create_user(
                username=data2["email"],
                email=data2["email"],
                password=data2["password"],
                document_type=partner.document_type,
                document_number=doc_number,
                phone=partner.phone,
            )

            partner.user = user
            partner.save()

        # --- Asignar compañías
        if data3 and data3.get("companies"):
            partner.companies.set(data3["companies"])

        # --- Limpiar sesión
        for k in ["partner_step1", "partner_step2", "partner_step3"]:
            request.session.pop(k, None)

        messages.success(request, "Partner creado exitosamente.")
        return redirect("billing:partner_list")