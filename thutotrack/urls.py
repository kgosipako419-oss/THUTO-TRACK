from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("teachers/", include("teachers.urls")),
    path("", RedirectView.as_view(pattern_name="teachers:dashboard", permanent=False)),
]
