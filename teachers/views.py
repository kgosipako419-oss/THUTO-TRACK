from collections import defaultdict
from datetime import date
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from core.models import Attendance, BehaviorNote, ClassGroup, Mark, Student, TeacherProfile, Term


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


# ---------------------------------------------------------------------------
# Bulk Excel upload of students into a class
# ---------------------------------------------------------------------------

BULK_UPLOAD_COLUMNS = [
    "student_number",
    "first_name",
    "last_name",
    "gender",
    "date_of_birth",
    "parent_name",
    "parent_phone",
]


@login_required
def bulk_upload_template(request, class_id: int):
    """Return an .xlsx template the teacher can fill in and re-upload."""
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)
    class_group = get_object_or_404(teacher.classes_taught, pk=class_id)

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="047857")
    for col, name in enumerate(BULK_UPLOAD_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.font = header_font
        cell.fill = header_fill

    ws.append([
        "S-2026-100",
        "Example",
        "Student",
        "F",
        "2010-03-15",
        "Mma Example",
        "+267 71 000 000",
    ])

    instructions = (
        "Required: student_number, first_name, last_name. "
        "gender = M/F/O. date_of_birth = YYYY-MM-DD. "
        "Delete the example row before uploading."
    )
    ws.cell(row=4, column=1, value=instructions).font = Font(italic=True, color="6B7280")

    for col_letter, width in zip("ABCDEFG", (16, 16, 16, 8, 14, 24, 20)):
        ws.column_dimensions[col_letter].width = width

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"students_template_{class_group.name.replace(' ', '_')}.xlsx"
    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _parse_bulk_upload(file, class_group, teacher):
    """Read an uploaded .xlsx and return (created_students, errors).

    Errors is a list of (row_number, message) tuples. The whole upload is
    wrapped in a transaction by the caller, so a non-empty errors list means
    nothing was written.
    """
    from openpyxl import load_workbook

    try:
        wb = load_workbook(file, read_only=True, data_only=True)
    except Exception as exc:
        return [], [(0, f"Could not read file: {exc}")]

    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    try:
        header = [str(c).strip().lower() if c is not None else "" for c in next(rows)]
    except StopIteration:
        return [], [(0, "Spreadsheet is empty.")]

    missing = [c for c in ("student_number", "first_name", "last_name") if c not in header]
    if missing:
        return [], [(0, f"Missing required column(s): {', '.join(missing)}")]

    idx = {name: header.index(name) for name in BULK_UPLOAD_COLUMNS if name in header}

    created = []
    errors = []
    seen_numbers = set()

    for row_num, row in enumerate(rows, start=2):
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue

        def cell(name):
            i = idx.get(name)
            if i is None or i >= len(row):
                return None
            v = row[i]
            return str(v).strip() if v is not None else None

        student_number = cell("student_number")
        first_name = cell("first_name")
        last_name = cell("last_name")

        if not student_number or not first_name or not last_name:
            errors.append((row_num, "student_number, first_name, last_name are required."))
            continue

        if student_number in seen_numbers:
            errors.append((row_num, f"Duplicate student_number '{student_number}' in upload."))
            continue
        seen_numbers.add(student_number)

        if Student.objects.filter(school=class_group.school, student_number=student_number).exists():
            errors.append((row_num, f"Student '{student_number}' already exists in this school."))
            continue

        gender = (cell("gender") or "").upper()[:1]
        if gender and gender not in {"M", "F", "O"}:
            errors.append((row_num, f"Invalid gender '{gender}'. Use M, F or O."))
            continue

        dob = None
        dob_raw = cell("date_of_birth")
        if dob_raw:
            try:
                dob = date.fromisoformat(dob_raw[:10])
            except ValueError:
                errors.append((row_num, f"Invalid date_of_birth '{dob_raw}'. Use YYYY-MM-DD."))
                continue

        created.append(
            Student(
                school=class_group.school,
                student_number=student_number,
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=dob,
                class_group=class_group,
                parent_name=cell("parent_name") or "",
                parent_phone=cell("parent_phone") or "",
            )
        )

    return created, errors


@login_required
def bulk_upload_students(request, class_id: int):
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)
    class_group = get_object_or_404(teacher.classes_taught.select_related("school"), pk=class_id)

    errors = []
    created_count = 0

    if request.method == "POST":
        uploaded = request.FILES.get("file")
        if not uploaded:
            errors = [(0, "Please choose an .xlsx file to upload.")]
        elif not uploaded.name.lower().endswith(".xlsx"):
            errors = [(0, "File must be an .xlsx workbook.")]
        else:
            to_create, errors = _parse_bulk_upload(uploaded, class_group, teacher)
            if not errors:
                try:
                    with transaction.atomic():
                        Student.objects.bulk_create(to_create)
                    created_count = len(to_create)
                    messages.success(
                        request,
                        f"Added {created_count} student(s) to {class_group.name}.",
                    )
                    return redirect("teachers:class_detail", class_id=class_group.id)
                except IntegrityError as exc:
                    errors = [(0, f"Database rejected upload: {exc}")]

    return render(
        request,
        "teachers/bulk_upload.html",
        {
            "class_group": class_group,
            "errors": errors,
            "columns": BULK_UPLOAD_COLUMNS,
        },
    )


# ---------------------------------------------------------------------------
# Student profile (full history view)
# ---------------------------------------------------------------------------

@login_required
def student_detail(request, student_id: int):
    teacher = _teacher_or_403(request)
    if not teacher:
        return render(request, "teachers/no_profile.html", status=403)

    student = get_object_or_404(
        Student.objects.select_related("class_group", "school"),
        pk=student_id,
        school=teacher.school,
        class_group__in=teacher.classes_taught.all(),
    )

    year = now().year

    marks_qs = (
        Mark.objects.filter(student=student)
        .select_related("subject", "teacher__user")
        .order_by("subject__name", "term", "-recorded_at")
    )
    marks_by_subject = defaultdict(list)
    for m in marks_qs:
        marks_by_subject[m.subject].append(m)

    subject_averages = []
    for subject, marks in marks_by_subject.items():
        avg = sum(m.percentage for m in marks) / len(marks)
        subject_averages.append({"subject": subject, "average": avg, "count": len(marks)})
    subject_averages.sort(key=lambda r: r["subject"].name)

    attendance_qs = Attendance.objects.filter(student=student, date__year=year)
    attendance_counts = {label: 0 for _, label in Attendance.Status.choices}
    status_to_label = dict(Attendance.Status.choices)
    for a in attendance_qs:
        attendance_counts[status_to_label[a.status]] += 1
    total_recorded = sum(attendance_counts.values())
    present_count = attendance_counts.get("Present", 0)
    attendance_rate = (present_count / total_recorded * 100) if total_recorded else None

    recent_attendance = Attendance.objects.filter(student=student).order_by("-date")[:10]
    behavior_notes = (
        BehaviorNote.objects.filter(student=student)
        .select_related("teacher__user")
        .order_by("-recorded_at")[:20]
    )

    return render(
        request,
        "teachers/student_detail.html",
        {
            "student": student,
            "marks_by_subject": dict(marks_by_subject),
            "subject_averages": subject_averages,
            "attendance_counts": attendance_counts,
            "attendance_rate": attendance_rate,
            "total_recorded": total_recorded,
            "recent_attendance": recent_attendance,
            "behavior_notes": behavior_notes,
            "year": year,
        },
    )
