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
    path("classes/<int:class_id>/upload/", views.bulk_upload_students, name="bulk_upload_students"),
    path("classes/<int:class_id>/upload/template/", views.bulk_upload_template, name="bulk_upload_template"),
    path("students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("students/<int:student_id>/edit/", views.student_edit, name="student_edit"),
    path("students/<int:student_id>/delete/", views.student_delete, name="student_delete"),
    path("classes/<int:class_id>/students/new/", views.student_create, name="student_create"),
    path("students/<int:student_id>/report/", views.student_term_report, name="student_term_report"),
    path("students/<int:student_id>/behavior/add/", views.add_behavior_note, name="add_behavior_note"),
    path("classes/<int:class_id>/reports/", views.class_term_reports, name="class_term_reports"),

    path("subjects/", views.subjects_manage, name="subjects_manage"),
    path("classes/new/", views.class_create, name="class_create"),
    path("calendar/", views.school_calendar, name="school_calendar"),

    path("enquiries/", views.enquiry_list, name="enquiry_list"),
    path("enquiries/new/", views.enquiry_create, name="enquiry_create"),
    path("enquiries/<int:enquiry_id>/", views.enquiry_detail, name="enquiry_detail"),
]
