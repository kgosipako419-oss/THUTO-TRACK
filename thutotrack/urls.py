from django.contrib import admin
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import include, path


def healthz(request):
    """Health probe for the platform (Render pings this).

    Returns 200 only when the DB is reachable so a half-broken deploy fails fast.
    """
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception as exc:
        return HttpResponse(f"db unreachable: {exc}", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


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
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("teachers/", include("teachers.urls")),
    path("admin-portal/", include("schooladmin.urls")),
    path("", include("parents.urls")),
    path("", home, name="core_home"),
]
