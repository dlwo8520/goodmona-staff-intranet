from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

def is_manager(user):
    return user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser)

def manager_required(view):
    @login_required
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied('관리자 권한이 필요합니다.')
        return view(request, *args, **kwargs)
    return guarded
