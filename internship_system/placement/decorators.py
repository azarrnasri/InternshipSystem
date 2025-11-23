from django.shortcuts import redirect
from functools import wraps

def role_required(allowed_roles=[]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')  # not logged in
            if request.user.role not in allowed_roles:
                return redirect('dashboard')  # wrong role, send to dashboard redirect
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator