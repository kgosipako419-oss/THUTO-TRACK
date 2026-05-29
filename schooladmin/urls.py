from django.urls import path

from . import views

app_name = "schooladmin"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("enquiries/", views.enquiries, name="enquiries"),
    path("enquiries/<int:enquiry_id>/", views.enquiry_detail, name="enquiry_detail"),

    path("teachers/", views.teachers, name="teachers"),
    path("teachers/new/", views.teacher_create, name="teacher_create"),
    path("teachers/<int:profile_id>/edit/", views.teacher_edit, name="teacher_edit"),

    path("students/", views.students, name="students"),

    path("classes/", views.classes, name="classes"),
    path("classes/new/", views.class_create, name="class_create"),
    path("classes/<int:class_id>/edit/", views.class_edit, name="class_edit"),

    path("subjects/", views.subjects, name="subjects"),

    path("calendar/", views.school_calendar, name="calendar"),

    path("school/", views.school_profile, name="school_profile"),

    path("parents/", views.parents_manage, name="parents"),
    path("parents/set-pin/", views.parent_set_pin, name="parent_set_pin"),

    path("exports/", views.exports, name="exports"),
    path("exports/download/", views.exports_download, name="exports_download"),
]
