from django import forms
from billing.models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        # fields = ["name", "vat", "email", "sequence", "active"]
        fields = "__all__"

        widgets = {
            # "name": forms.TextInput(attrs={"class": "form-control"}),
            # "vat": forms.TextInput(attrs={"class": "form-control"}),
            "partner": forms.Select(attrs={"class": "form-select"}),
            "sequence": forms.TextInput(attrs={"class": "form-control"}),
            "report_header": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "report_footer": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "tax_calculation_rounding_method": forms.Select(
                attrs={"class": "form-select"}
            ),
            "account_tax_periodicity": forms.Select(attrs={"class": "form-select"}),
            "account_tax_periodicity_reminder_day": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
            "sunat_amount": forms.NumberInput(attrs={"class": "form-control"}),
            "currency_provider": forms.TextInput(attrs={"class": "form-control"}),
            "theme_color": forms.TextInput(attrs={"class": "form-control"}),
            "theme_text_color": forms.TextInput(attrs={"class": "form-control"}),
            "text_color": forms.TextInput(attrs={"class": "form-control"}),
            "company_color": forms.TextInput(attrs={"class": "form-control"}),
            "bank_comment": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_partner(self):
        partner = self.cleaned_data.get("partner")

        # Validación 1: debe existir
        if not partner:
            raise forms.ValidationError("Debe seleccionar un partner válido.")

        # Validación 2: solo partners marcados como empresa pueden ser compañías
        if not partner.is_company:
            raise forms.ValidationError(
                "Solo partners marcados como empresa (is_company=True) pueden ser usados para crear una compañía."
            )

        return partner
