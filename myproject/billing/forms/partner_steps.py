from django import forms
from billing.models import Partner, Company


#  PASO 1 – Datos Básicos 
class PartnerStep1Form(forms.ModelForm):
    class Meta:
        model = Partner
        fields = [
            "name", "display_name", "document_type", "num_document",
            "email", "phone",
            "is_customer", "is_supplier", "is_company",
            "parent",
        ]


#  PASO 2 – Datos de Usuario 
class PartnerStep2Form(forms.Form):
    create_user = forms.BooleanField(
        required=False,
        label="Crear usuario asociado"
    )
    email = forms.EmailField(required=False, label="Email de acceso")
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="Contraseña"
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("create_user"):
            if not cleaned.get("email"):
                self.add_error("email", "El email es obligatorio si se creará usuario.")
            if not cleaned.get("password"):
                self.add_error("password", "Debe ingresar una contraseña.")
        return cleaned


#  PASO 3 – Asignar Compañías 
class PartnerStep3Form(forms.Form):
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Compañías asociadas"
    )
