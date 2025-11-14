from django import forms
from users.models import User

class PartnerStep2UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    class Meta:
        model = User
        fields = ["username", "login", "email", "phone"]
