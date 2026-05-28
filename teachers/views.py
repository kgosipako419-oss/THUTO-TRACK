from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from core.models import Attendance, ClassGroup, Mark, Student, TeacherProfile, Term


def _teacher_or_403(request):
    """Return the request user's TeacherProfile or None if they don't have one."""
    return TeacherProfile.objects.select_related("school").filter(user=request.user).first()


@login_required
def dashboard(request):
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)

    classes = teacher.classes_taught.select_related("school").all()
    today_attendance_count = Attendance.objects.filter(
        recorded_by=teacher,
        date=date.today(),
    ).count()
    recent_marks = (
        Mark.objects.filter(teacher=teacher)
        .select_related("student", "subject")
        .order_by("-recorded_at")[:10]
    )

    return render(
        request,
        "teachers/dashboard.html",
        {
            "teacher": teacher,
            "classes": classes,
            "today_attendance_count": today_attendance_count,
            "recent_marks": recent_marks,
        },
    )


@login_required
def class_list(request):
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)
    classes = teacher.classes_taught.select_related("school").all()
    return render(request, "teachers/class_list.html", {"classes": classes})


@login_required
def class_detail(request, class_id: int):
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)
    class_group = get_object_or_404(teacher.classes_taught, pk=class_id)
    students = class_group.students.filter(is_active=True)
    return render(
        request,
        "teachers/class_detail.html",
        {"class_group": class_group, "students": students},
    )


@login_required
def enter_marks(request, class_id: int):
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)
    class_group = get_object_or_404(teacher.classes_taught, pk=class_id)
    students = class_group.students.filter(is_active=True)
    subjects = teacher.subjects.all()

    if request.method == "POST":
        subject_id = request.POST.get("subject")
        title = request.POST.get("title", "").strip()
        assessment_type = request.POST.get("assessment_type", Mark.AssessmentType.TEST)
        max_score = request.POST.get("max_score") or 100
        term = int(request.POST.get("term") or Term.TERM_1)
        academic_year = int(request.POST.get("academic_year") or now().year)

        if not subject_id or not title:
            messages.error(request, "Subject and assessment title are required.")
        else:
            created = 0
            for student in students:
                raw = request.POST.get(f"score_{student.id}")
                if raw is None or raw.strip() == "":
                    continue
                try:
                    score = float(raw)
                except ValueError:
                    continue
                Mark.objects.create(
                    student=student,
                    subject_id=subject_id,
                    teacher=teacher,
                    assessment_type=assessment_type,
                    title=title,
                    score=score,
                    max_score=max_score,
                    term=term,
                    academic_year=academic_year,
                )
                created += 1
            messages.success(request, f"Recorded {created} mark(s) for '{title}'.")
            return redirect("teachers:class_detail", class_id=class_group.id)

    return render(
        request,
        "teachers/enter_marks.html",
        {
            "class_group": class_group,
            "students": students,
            "subjects": subjects,
            "terms": Term.choices,
            "assessment_types": Mark.AssessmentType.choices,
            "current_year": now().year,
        },
    )


@login_required
def enter_attendance(request, class_id: int):
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)
    class_group = get_object_or_404(teacher.classes_taught, pk=class_id)
    students = class_group.students.filter(is_active=True)

    if request.method == "POST":
        att_date_raw = request.POST.get("date") or date.today().isoformat()
        try:
            att_date = date.fromisoformat(att_date_raw)
        except ValueError:
            att_date = date.today()

        recorded = 0
        for student in students:
            status = request.POST.get(f"status_{student.id}")
            if not status:
                continue
            Attendance.objects.update_or_create(
                student=student,
                date=att_date,
                defaults={"status": status, "recorded_by": teacher},
            )
            recorded += 1
        messages.success(request, f"Attendance saved for {recorded} student(s) on {att_date}.")
        return redirect("teachers:class_detail", class_id=class_group.id)

    return render(
        request,
        "teachers/enter_attendance.html",
        {
            "class_group": class_group,
            "students": students,
            "today": date.today().isoformat(),
            "statuses": Attendance.Status.choices,
        },
    )
