from formtools.wizard.views import SessionWizardView
from django.shortcuts import redirect
from billing.forms.partner_step1 import PartnerStep1Form
from billing.forms.partner_step2_user import PartnerStep2UserForm
from billing.models import Partner
from users.models import User


FORMS = [
    ("step1", PartnerStep1Form),
    ("step2_user", PartnerStep2UserForm),
]

class PartnerWizard(SessionWizardView):
    form_list = FORMS
    template_name = "billing/partner/wizard/step.html"

    def get_form_step_data(self, step):
        return self.get_cleaned_data_for_step(step)

    def get_form_instance(self, step):
        return None

    def get_next_step(self, step, form=None):
        """Controla la bifurcación hacia paso 2 solo si marcó usuario del sistema."""
        if step == "step1":
            data = self.get_cleaned_data_for_step("step1")
            if data and data.get("is_system_user"):
                return "step2_user"
            return self.steps.next
        return super().get_next_step(step, form)

    def done(self, form_list, **kwargs):
        data1 = self.get_cleaned_data_for_step("step1")

        # 1. Crear Partner
        partner = Partner.objects.create(
            name=data1["name"],
            display_name=data1["display_name"],
            email=data1["email"],
            document_type=data1["document_type"],
            num_document=data1["num_document"],
            phone=data1["phone"],
            is_company=data1["is_company"],
            is_customer=data1["is_customer"],
            is_supplier=data1["is_supplier"],
        )
        partner.companies.set(data1["companies"])

        # 2. Crear usuario si aplica
        if data1["is_system_user"]:
            data2 = self.get_cleaned_data_for_step("step2_user")

            user = User.objects.create_user(
                username=data2["username"],
                login=data2["login"],
                email=data2["email"],
                phone=data2["phone"],
                password=data2["password"],
            )

            partner.user = user
            partner.save()

        return redirect("billing:partner_detail", pk=partner.id)
