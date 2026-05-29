from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Attendance,
    BehaviorNote,
    ClassGroup,
    Enquiry,
    Mark,
    ParentSession,
    School,
    SchoolAdminProfile,
    Student,
    Subject,
    TeacherProfile,
    TermSchedule,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("ThutoTrack", {"fields": ("role", "phone")}),
    )
    list_display = ("username", "first_name", "last_name", "email", "role", "is_active")
    list_filter = BaseUserAdmin.list_filter + ("role",)


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "region", "principal_name", "phone")
    search_fields = ("name", "code", "region")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "school")
    list_filter = ("school",)
    search_fields = ("name", "code")


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "grade_level", "academic_year", "school", "class_teacher")
    list_filter = ("school", "academic_year", "grade_level")
    search_fields = ("name",)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "employee_id", "is_active")
    list_filter = ("school", "is_active")
    search_fields = ("user__username", "user__first_name", "user__last_name", "employee_id")
    filter_horizontal = ("subjects", "classes_taught")


@admin.register(SchoolAdminProfile)
class SchoolAdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "title", "employee_id")
    list_filter = ("school",)
    search_fields = ("user__username", "user__first_name", "user__last_name", "title")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("student_number", "first_name", "last_name", "class_group", "school", "is_active")
    list_filter = ("school", "class_group", "is_active", "gender")
    search_fields = ("student_number", "first_name", "last_name", "parent_phone")


@admin.register(Mark)
class MarkAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "assessment_type", "title", "score", "max_score", "term", "academic_year")
    list_filter = ("subject", "assessment_type", "term", "academic_year")
    search_fields = ("student__first_name", "student__last_name", "title")
    autocomplete_fields = ("student", "subject", "teacher")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "date", "status", "recorded_by")
    list_filter = ("status", "date")
    search_fields = ("student__first_name", "student__last_name")
    autocomplete_fields = ("student", "recorded_by")
    date_hierarchy = "date"


@admin.register(BehaviorNote)
class BehaviorNoteAdmin(admin.ModelAdmin):
    list_display = ("student", "category", "teacher", "recorded_at")
    list_filter = ("category",)
    search_fields = ("student__first_name", "student__last_name", "note")
    autocomplete_fields = ("student", "teacher")


@admin.register(TermSchedule)
class TermScheduleAdmin(admin.ModelAdmin):
    list_display = ("school", "academic_year", "term", "start_date", "end_date")
    list_filter = ("school", "academic_year")
    ordering = ("school", "academic_year", "term")


@admin.register(ParentSession)
class ParentSessionAdmin(admin.ModelAdmin):
    list_display = ("phone", "selected_student", "message_count", "last_message_at")
    search_fields = ("phone",)
    readonly_fields = ("last_message_at",)


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("subject", "school", "from_teacher", "category", "status", "created_at")
    list_filter = ("status", "category", "school")
    search_fields = ("subject", "body", "from_teacher__user__username")
    autocomplete_fields = ("from_teacher",)
    readonly_fields = ("created_at", "updated_at", "school", "from_teacher", "subject", "body", "category")
    fields = ("school", "from_teacher", "category", "subject", "body", "status", "response", "resolved_at", "created_at", "updated_at")
