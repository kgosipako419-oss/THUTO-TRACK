from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import include, path


@login_required
def home(request):
    """Route logged-in users to the right portal based on their profile."""
    if hasattr(request.user, "school_admin_profile"):
        return redirect("schooladmin:dashboard")
    if hasattr(request.user, "teacher_profile"):
        return redirect("teachers:dashboard")
    return redirect("teachers:dashboard")  # fall through to no-profile screen


urlpatterns = [
    path("admin/", admin.site.urls),
    path("teachers/", include("teachers.urls")),
    path("admin-portal/", include("schooladmin.urls")),
    path("", home, name="core_home"),
]
