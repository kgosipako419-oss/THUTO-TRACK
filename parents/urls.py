from django.urls import path

from . import views

app_name = "parents"

urlpatterns = [
    path("whatsapp/webhook/", views.whatsapp_webhook, name="whatsapp_webhook"),

    path("parents/login/", views.parent_login, name="login"),
    path("parents/logout/", views.parent_logout, name="logout"),
    path("parents/", views.dashboard, name="dashboard"),
    path("parents/students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("parents/students/<int:student_id>/report/", views.student_report, name="student_report"),
]
