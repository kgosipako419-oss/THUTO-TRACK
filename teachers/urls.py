from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "teachers"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="teachers/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("classes/", views.class_list, name="class_list"),
    path("classes/<int:class_id>/", views.class_detail, name="class_detail"),
    path("classes/<int:class_id>/marks/", views.enter_marks, name="enter_marks"),
    path("classes/<int:class_id>/attendance/", views.enter_attendance, name="enter_attendance"),
]
