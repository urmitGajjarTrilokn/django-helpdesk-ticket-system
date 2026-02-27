from django import template
from django.core.exceptions import ObjectDoesNotExist


register = template.Library()


@register.filter
def avatar_url(user):
    if not user:
        return ''
    try:
        profile = user.userprofile
    except ObjectDoesNotExist:
        return ''
    image = getattr(profile, 'Profile_Image', None)
    if not image:
        return ''
    try:
        return image.url
    except Exception:
        return ''


@register.filter
def avatar_initial(user):
    if not user:
        return '?'
    username = (getattr(user, 'username', '') or '').strip()
    if username:
        return username[0].upper()
    full_name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    if full_name:
        return full_name[0].upper()
    return '?'
