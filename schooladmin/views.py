from datetime import date
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Avg, Count, F, FloatField, Q
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from core.models import (
    Attendance,
    ClassGroup,
    Enquiry,
    Mark,
    School,
    SchoolAdminProfile,
    Student,
    Subject,
    TeacherProfile,
    TermSchedule,
    User,
)


def _admin_or_403(request):
    return (
        SchoolAdminProfile.objects.select_related("school")
        .filter(user=request.user)
        .first()
    )


def _common_context(admin):
    return {
        "admin": admin,
        "school": admin.school,
        "open_enquiries_count": Enquiry.objects.filter(
            school=admin.school, status=Enquiry.Status.OPEN,
        ).count(),
    }


def _require_admin(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        admin = _admin_or_403(request)
        if not admin:
            return render(request, "schooladmin/no_access.html", status=403)
        return view(request, admin, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@_require_admin
def dashboard(request, admin):
    school = admin.school
    year = now().year

    teacher_count = TeacherProfile.objects.filter(school=school, is_active=True).count()
    student_count = Student.objects.filter(school=school, is_active=True).count()
    class_count = ClassGroup.objects.filter(school=school).count()
    subject_count = Subject.objects.filter(school=school).count()

    enquiry_qs = Enquiry.objects.filter(school=school)
    open_enquiries = enquiry_qs.filter(status=Enquiry.Status.OPEN).count()
    in_progress = enquiry_qs.filter(status=Enquiry.Status.IN_PROGRESS).count()

    recent_enquiries = enquiry_qs.select_related("from_teacher__user").order_by("-created_at")[:5]

    marks_qs = Mark.objects.filter(student__school=school, academic_year=year).annotate(
        pct=Cast(F("score"), FloatField()) * 100.0 / Cast(F("max_score"), FloatField()),
    )
    overall_stats = marks_qs.aggregate(
        avg_pct=Avg("pct"), assessment_count=Count("id"),
    )

    by_subject = list(
        marks_qs.values("subject__id", "subject__name")
        .annotate(avg_pct=Avg("pct"), assessment_count=Count("id"))
        .order_by("subject__name")
    )

    att_qs = Attendance.objects.filter(student__school=school, date__year=year)
    att_total = att_qs.count()
    att_present = att_qs.filter(status="P").count()
    attendance_rate = (att_present / att_total * 100) if att_total else None

    return render(
        request,
        "schooladmin/dashboard.html",
        {
            **_common_context(admin),
            "year": year,
            "teacher_count": teacher_count,
            "student_count": student_count,
            "class_count": class_count,
            "subject_count": subject_count,
            "open_enquiries": open_enquiries,
            "in_progress_enquiries": in_progress,
            "recent_enquiries": recent_enquiries,
            "overall_avg": overall_stats.get("avg_pct"),
            "overall_assessments": overall_stats.get("assessment_count") or 0,
            "by_subject": by_subject,
            "attendance_rate": attendance_rate,
        },
    )


# ---------------------------------------------------------------------------
# Enquiries
# ---------------------------------------------------------------------------

@_require_admin
def enquiries(request, admin):
    qs = Enquiry.objects.filter(school=admin.school).select_related("from_teacher__user")
    status_filter = request.GET.get("status", "")
    if status_filter and status_filter in dict(Enquiry.Status.choices):
        qs = qs.filter(status=status_filter)
    category_filter = request.GET.get("category", "")
    if category_filter and category_filter in dict(Enquiry.Category.choices):
        qs = qs.filter(category=category_filter)

    return render(
        request,
        "schooladmin/enquiries.html",
        {
            **_common_context(admin),
            "enquiries": qs.order_by("-created_at"),
            "status_filter": status_filter,
            "category_filter": category_filter,
            "statuses": Enquiry.Status.choices,
            "categories": Enquiry.Category.choices,
        },
    )


@_require_admin
def enquiry_detail(request, admin, enquiry_id: int):
    enquiry = get_object_or_404(
        Enquiry.objects.select_related("from_teacher__user"),
        pk=enquiry_id,
        school=admin.school,
    )
    if request.method == "POST":
        new_status = request.POST.get("status")
        response_text = (request.POST.get("response") or "").strip()
        if new_status not in dict(Enquiry.Status.choices):
            messages.error(request, "Invalid status.")
        else:
            enquiry.status = new_status
            enquiry.response = response_text
            if new_status == Enquiry.Status.RESOLVED and not enquiry.resolved_at:
                enquiry.resolved_at = now()
            elif new_status != Enquiry.Status.RESOLVED:
                enquiry.resolved_at = None
            enquiry.save()
            messages.success(request, "Enquiry updated. Teacher will see the response.")
            return redirect("schooladmin:enquiry_detail", enquiry_id=enquiry.id)

    return render(
        request,
        "schooladmin/enquiry_detail.html",
        {
            **_common_context(admin),
            "enquiry": enquiry,
            "statuses": Enquiry.Status.choices,
        },
    )


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------

@_require_admin
def teachers(request, admin):
    qs = (
        TeacherProfile.objects.filter(school=admin.school)
        .select_related("user")
        .prefetch_related("subjects", "classes_taught")
    )
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(employee_id__icontains=search)
        )
    return render(
        request,
        "schooladmin/teachers.html",
        {**_common_context(admin), "teachers": qs, "search": search},
    )


@_require_admin
def teacher_create(request, admin):
    errors = {}
    subjects = Subject.objects.filter(school=admin.school).order_by("name")
    classes = ClassGroup.objects.filter(school=admin.school).order_by("-academic_year", "name")

    if request.method == "POST":
        first = (request.POST.get("first_name") or "").strip()
        last = (request.POST.get("last_name") or "").strip()
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        password = (request.POST.get("password") or "").strip()
        employee_id = (request.POST.get("employee_id") or "").strip()
        subject_ids = request.POST.getlist("subjects")
        class_ids = request.POST.getlist("classes")

        if not first:
            errors["first_name"] = "First name is required."
        if not last:
            errors["last_name"] = "Last name is required."
        if not username:
            errors["username"] = "Username is required."
        elif User.objects.filter(username=username).exists():
            errors["username"] = "That username is already taken."
        if not password or len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."

        if not errors:
            with transaction.atomic():
                user = User.objects.create(
                    username=username,
                    first_name=first,
                    last_name=last,
                    email=email,
                    phone=phone,
                    role=User.Role.TEACHER,
                    password=make_password(password),
                )
                profile = TeacherProfile.objects.create(
                    user=user, school=admin.school, employee_id=employee_id,
                )
                if subject_ids:
                    profile.subjects.set(
                        Subject.objects.filter(school=admin.school, id__in=subject_ids)
                    )
                if class_ids:
                    profile.classes_taught.set(
                        ClassGroup.objects.filter(school=admin.school, id__in=class_ids)
                    )
            messages.success(request, f"Created teacher {first} {last} ({username}).")
            return redirect("schooladmin:teachers")

    return render(
        request,
        "schooladmin/teacher_form.html",
        {
            **_common_context(admin),
            "errors": errors,
            "values": request.POST if request.method == "POST" else {},
            "subjects": subjects,
            "classes": classes,
            "selected_subject_ids": set(),
            "selected_class_ids": set(),
            "is_active_checked": True,
            "mode": "create",
        },
    )


@_require_admin
def teacher_edit(request, admin, profile_id: int):
    profile = get_object_or_404(
        TeacherProfile.objects.select_related("user"),
        pk=profile_id,
        school=admin.school,
    )
    subjects = Subject.objects.filter(school=admin.school).order_by("name")
    classes = ClassGroup.objects.filter(school=admin.school).order_by("-academic_year", "name")

    if request.method == "POST":
        profile.user.first_name = (request.POST.get("first_name") or "").strip()
        profile.user.last_name = (request.POST.get("last_name") or "").strip()
        profile.user.email = (request.POST.get("email") or "").strip()
        profile.user.phone = (request.POST.get("phone") or "").strip()
        profile.user.save()
        profile.employee_id = (request.POST.get("employee_id") or "").strip()
        profile.is_active = bool(request.POST.get("is_active"))
        profile.save()

        subject_ids = request.POST.getlist("subjects")
        class_ids = request.POST.getlist("classes")
        profile.subjects.set(
            Subject.objects.filter(school=admin.school, id__in=subject_ids)
        )
        profile.classes_taught.set(
            ClassGroup.objects.filter(school=admin.school, id__in=class_ids)
        )

        new_password = (request.POST.get("password") or "").strip()
        if new_password:
            if len(new_password) < 8:
                messages.error(request, "Password unchanged: must be at least 8 characters.")
            else:
                profile.user.password = make_password(new_password)
                profile.user.save()
                messages.success(request, "Password updated.")

        messages.success(request, f"Updated {profile.user.get_full_name() or profile.user.username}.")
        return redirect("schooladmin:teachers")

    return render(
        request,
        "schooladmin/teacher_form.html",
        {
            **_common_context(admin),
            "profile": profile,
            "values": {
                "first_name": profile.user.first_name,
                "last_name": profile.user.last_name,
                "username": profile.user.username,
                "email": profile.user.email,
                "phone": profile.user.phone,
                "employee_id": profile.employee_id,
            },
            "errors": {},
            "subjects": subjects,
            "classes": classes,
            "selected_subject_ids": set(profile.subjects.values_list("id", flat=True)),
            "selected_class_ids": set(profile.classes_taught.values_list("id", flat=True)),
            "is_active_checked": profile.is_active,
            "mode": "edit",
        },
    )


# ---------------------------------------------------------------------------
# Students (read-only cross-class view)
# ---------------------------------------------------------------------------

@_require_admin
def students(request, admin):
    qs = Student.objects.filter(school=admin.school).select_related("class_group")
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(student_number__icontains=search)
            | Q(parent_phone__icontains=search)
        )
    class_filter = request.GET.get("class", "")
    if class_filter:
        try:
            qs = qs.filter(class_group_id=int(class_filter))
        except ValueError:
            pass
    status_filter = request.GET.get("status", "")
    if status_filter == "active":
        qs = qs.filter(is_active=True)
    elif status_filter == "inactive":
        qs = qs.filter(is_active=False)

    return render(
        request,
        "schooladmin/students.html",
        {
            **_common_context(admin),
            "students": qs.order_by("class_group__name", "last_name", "first_name"),
            "all_classes": ClassGroup.objects.filter(school=admin.school).order_by("-academic_year", "name"),
            "search": search,
            "class_filter": class_filter,
            "status_filter": status_filter,
        },
    )


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@_require_admin
def classes(request, admin):
    qs = (
        ClassGroup.objects.filter(school=admin.school)
        .select_related("class_teacher__user")
        .annotate(active_student_count=Count("students", filter=Q(students__is_active=True)))
    )
    year_filter = request.GET.get("year", "")
    if year_filter:
        try:
            qs = qs.filter(academic_year=int(year_filter))
        except ValueError:
            pass

    available_years = list(
        ClassGroup.objects.filter(school=admin.school)
        .values_list("academic_year", flat=True)
        .distinct()
        .order_by("-academic_year")
    )

    return render(
        request,
        "schooladmin/classes.html",
        {
            **_common_context(admin),
            "classes": qs.order_by("-academic_year", "grade_level", "name"),
            "available_years": available_years,
            "year_filter": year_filter,
        },
    )


def _save_class_form(request, admin, instance=None):
    errors = {}
    name = (request.POST.get("name") or "").strip()
    try:
        grade_level = int(request.POST.get("grade_level") or 0)
    except ValueError:
        grade_level = 0
    try:
        academic_year = int(request.POST.get("academic_year") or now().year)
    except ValueError:
        academic_year = now().year
    class_teacher_id = request.POST.get("class_teacher") or ""

    if not name:
        errors["name"] = "Name is required."
    if grade_level <= 0:
        errors["grade_level"] = "Grade level must be a positive number."

    if not errors:
        duplicate = ClassGroup.objects.filter(
            school=admin.school, name=name, academic_year=academic_year,
        )
        if instance:
            duplicate = duplicate.exclude(pk=instance.pk)
        if duplicate.exists():
            errors["name"] = f"A class named '{name}' already exists for {academic_year}."

    if errors:
        return None, errors

    class_teacher = None
    if class_teacher_id:
        class_teacher = TeacherProfile.objects.filter(
            pk=class_teacher_id, school=admin.school,
        ).first()

    if instance is None:
        instance = ClassGroup(school=admin.school)
    instance.name = name
    instance.grade_level = grade_level
    instance.academic_year = academic_year
    instance.class_teacher = class_teacher
    instance.save()
    if class_teacher:
        class_teacher.classes_taught.add(instance)
    return instance, {}


@_require_admin
def class_create(request, admin):
    errors = {}
    if request.method == "POST":
        instance, errors = _save_class_form(request, admin)
        if not errors:
            messages.success(request, f"Created class '{instance.name}'.")
            return redirect("schooladmin:classes")

    return render(
        request,
        "schooladmin/class_form.html",
        {
            **_common_context(admin),
            "errors": errors,
            "values": request.POST if request.method == "POST" else {"academic_year": now().year},
            "teachers": TeacherProfile.objects.filter(school=admin.school, is_active=True).select_related("user"),
            "mode": "create",
        },
    )


@_require_admin
def class_edit(request, admin, class_id: int):
    class_group = get_object_or_404(ClassGroup, pk=class_id, school=admin.school)
    errors = {}
    if request.method == "POST":
        _, errors = _save_class_form(request, admin, instance=class_group)
        if not errors:
            messages.success(request, f"Updated class '{class_group.name}'.")
            return redirect("schooladmin:classes")

    values = request.POST if request.method == "POST" else {
        "name": class_group.name,
        "grade_level": class_group.grade_level,
        "academic_year": class_group.academic_year,
        "class_teacher": str(class_group.class_teacher_id or ""),
    }
    return render(
        request,
        "schooladmin/class_form.html",
        {
            **_common_context(admin),
            "errors": errors,
            "values": values,
            "teachers": TeacherProfile.objects.filter(school=admin.school).select_related("user"),
            "class_group": class_group,
            "mode": "edit",
        },
    )


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

@_require_admin
def subjects(request, admin):
    errors = {}
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        code = (request.POST.get("code") or "").strip().upper()
        if not name or not code:
            errors["form"] = "Name and code are required."
        elif Subject.objects.filter(school=admin.school, code=code).exists():
            errors["form"] = f"A subject with code '{code}' already exists."
        else:
            Subject.objects.create(school=admin.school, name=name, code=code)
            messages.success(request, f"Added subject '{name}'.")
            return redirect("schooladmin:subjects")

    subject_qs = (
        Subject.objects.filter(school=admin.school)
        .annotate(teacher_count=Count("teachers"))
        .order_by("name")
    )

    return render(
        request,
        "schooladmin/subjects.html",
        {
            **_common_context(admin),
            "subjects": subject_qs,
            "errors": errors,
            "values": request.POST if request.method == "POST" else {},
        },
    )


# ---------------------------------------------------------------------------
# School profile
# ---------------------------------------------------------------------------

@_require_admin
def school_profile(request, admin):
    school = admin.school
    errors = {}
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            errors["name"] = "School name is required."
        elif School.objects.filter(name=name).exclude(pk=school.pk).exists():
            errors["name"] = "Another school already uses that name."
        if not errors:
            school.name = name
            school.region = (request.POST.get("region") or "").strip()
            school.address = (request.POST.get("address") or "").strip()
            school.phone = (request.POST.get("phone") or "").strip()
            school.email = (request.POST.get("email") or "").strip()
            school.principal_name = (request.POST.get("principal_name") or "").strip()
            school.save()
            messages.success(request, "School profile saved.")
            return redirect("schooladmin:school_profile")

    return render(
        request,
        "schooladmin/school_profile.html",
        {**_common_context(admin), "errors": errors},
    )


# ---------------------------------------------------------------------------
# Term schedule (calendar)
# ---------------------------------------------------------------------------

def _parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return "INVALID"


@_require_admin
def school_calendar(request, admin):
    current_year = now().year
    try:
        year = int(request.GET.get("year") or current_year)
    except ValueError:
        year = current_year

    errors_per_term = {}

    if request.method == "POST":
        try:
            year = int(request.POST.get("year") or current_year)
        except ValueError:
            year = current_year

        row_changes = []
        for term_num in (1, 2, 3):
            start = _parse_date(request.POST.get(f"start_{term_num}"))
            end = _parse_date(request.POST.get(f"end_{term_num}"))
            if start == "INVALID" or end == "INVALID":
                errors_per_term[term_num] = "Invalid date format."
                continue
            if start is None and end is None:
                row_changes.append(("clear", term_num))
                continue
            if start is None or end is None:
                errors_per_term[term_num] = "Both start and end dates are required."
                continue
            if end < start:
                errors_per_term[term_num] = "End date must be on or after start date."
                continue
            row_changes.append(("upsert", term_num, start, end))

        if not errors_per_term:
            with transaction.atomic():
                for change in row_changes:
                    if change[0] == "clear":
                        TermSchedule.objects.filter(
                            school=admin.school, academic_year=year, term=change[1],
                        ).delete()
                    else:
                        _, term_num, start, end = change
                        TermSchedule.objects.update_or_create(
                            school=admin.school,
                            academic_year=year,
                            term=term_num,
                            defaults={"start_date": start, "end_date": end},
                        )
            messages.success(request, f"Calendar for {year} saved.")
            return redirect(f"{request.path}?year={year}")

    existing = {
        ts.term: ts
        for ts in TermSchedule.objects.filter(school=admin.school, academic_year=year)
    }
    term_rows = [
        {"num": n, "schedule": existing.get(n), "error": errors_per_term.get(n)}
        for n in (1, 2, 3)
    ]

    return render(
        request,
        "schooladmin/calendar.html",
        {
            **_common_context(admin),
            "year": year,
            "prev_year": year - 1,
            "next_year": year + 1,
            "current_year": current_year,
            "term_rows": term_rows,
        },
    )
