from .permissions import is_manager

def navigation(request):
    return {'is_manager': is_manager(request.user)}
