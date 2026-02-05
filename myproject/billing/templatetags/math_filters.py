# myproject/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplica el valor por el argumento"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

