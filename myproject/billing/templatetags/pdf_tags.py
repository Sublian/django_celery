# myproject/billing/templatetags/pdf_tags.py
from django import template

register = template.Library()

@register.simple_tag
def get_base_pdf_template():
    """Devuelve la ruta correcta al template base"""
    return 'shared/utils/pdf/templates/base_pdf.html'