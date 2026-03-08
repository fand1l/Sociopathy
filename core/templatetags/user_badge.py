from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def display_name(user):
    if not user:
        return ""
    username = getattr(user, "username", "")
    if not username:
        return ""
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return format_html(
            '{} <i class="bx bx-check-shield" style="color:#ff9e00;" aria-label="Адміністратор" title="Верифікований"></i>',
            username,
        )
    return username
