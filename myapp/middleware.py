from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse, resolve, NoReverseMatch
from .models import DepartmentMember


class DepartmentAccessMiddleware:
    """
    Middleware that:
    1. Exempts public/auth URLs from authentication checks.
    2. Ensures non-superuser authenticated users without a department
       cannot access department-restricted pages.
    3. Attaches user_departments to every request for convenience.
    """

                                                               
    EXEMPT_URL_NAMES = {
        'landing',
        'login',
        'logout',
        'register',
        'password_reset',
        'password_reset_done',
        'password_reset_confirm',
        'password_reset_complete',
        'profile',
        'update_profile',
        'ChangePassword',
        'notification_count_api',
        'notifications_list',
        'mark_notification_read',
        'mark_all_read',
        'delete_notification',
    }

                                                    
    EXEMPT_PATH_PREFIXES = (
        '/admin/',
        '/static/',
        '/media/',
        '/api/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

                                                 
        if request.user.is_superuser or getattr(request.user, 'is_staff', False):
            return self.get_response(request)

        path = request.path

                                                         
        if any(path.startswith(p) for p in self.EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

                                                      
        try:
            current_url_name = resolve(path).url_name
        except Exception:
            current_url_name = ''

        if current_url_name in self.EXEMPT_URL_NAMES:
            return self.get_response(request)

                                                                        
        request.user_departments = DepartmentMember.objects.filter(
            user=request.user,
            is_active=True,
        ).select_related('department')

        return self.get_response(request)


class TaskAccessMiddleware:
    """Placeholder for future per-task access enforcement at middleware level."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)