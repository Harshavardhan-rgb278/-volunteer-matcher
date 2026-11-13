from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Profile


def _role_required(role, message):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if profile is None or profile.role != role:
                messages.error(request, message)
                return redirect("dashboard")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


volunteer_required = _role_required(Profile.VOLUNTEER, "That page is for volunteers only.")
organizer_required = _role_required(Profile.ORGANIZER, "That page is for non-profit admins only.")
manager_required = _role_required(Profile.MANAGER, "That page is for managers only.")
