from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

def is_admin_user(user):
    if not user or not user.is_authenticated:
        return False
    return bool(
        user.is_staff
        or user.is_superuser
        or getattr(user, 'role', None) == 'admin'
    )

def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_admin_user(request.user):
            raise PermissionDenied('Доступ только для администратора')
        return view_func(request, *args, **kwargs)
    return _wrapped