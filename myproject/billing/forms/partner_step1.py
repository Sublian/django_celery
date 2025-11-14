from django import forms
from billing.models import Partner, Company

class PartnerStep1Form(forms.ModelForm):
    class Meta:
        model = Partner
        fields = [
            "name", "display_name", "email", "email_secondary",
            "document_type", "num_document", "phone", "mobile",
            "is_company", "is_customer", "is_supplier", "is_employee",
            "is_detractor", "is_partner_retention",
            "street", "street2",
            "companies",
        ]
        widgets = {
            "companies": forms.CheckboxSelectMultiple
        }

    is_system_user = forms.BooleanField(
        required=False,
        label="¿Es usuario del sistema?"
    )
