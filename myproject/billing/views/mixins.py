from django.shortcuts import redirect


class WizardSessionRequiredMixin:
    """
    Bloquea el acceso a un paso del wizard cuando la sesión del paso previo no existe.
    Cada vista define cuál clave de sesión requiere.
    """

    required_key = None

    def dispatch(self, request, *args, **kwargs):
        if self.required_key and not request.session.get(self.required_key):
            return redirect("billing:partner_wizard_step1")
        return super().dispatch(request, *args, **kwargs)
