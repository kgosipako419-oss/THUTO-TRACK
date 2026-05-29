from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import include, path


def home(request):
    """Anonymous users see the multi-section login landing page.

    Authenticated users are routed to the right portal based on their profile.
    """
    if not request.user.is_authenticated:
        return render(request, "landing.html")
    if hasattr(request.user, "school_admin_profile"):
        return redirect("schooladmin:dashboard")
    if hasattr(request.user, "teacher_profile"):
        return redirect("teachers:dashboard")
    if request.user.is_authenticated and getattr(request.user, "role", "") == "PARENT":
        return redirect("parents:dashboard")
    if request.user.is_superuser:
        return redirect("/admin/")
    return render(request, "teachers/no_profile.html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("teachers/", include("teachers.urls")),
    path("admin-portal/", include("schooladmin.urls")),
    path("", include("parents.urls")),
    path("", home, name="core_home"),
]
