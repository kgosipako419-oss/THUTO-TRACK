"""PDF term report generation using ReportLab.

Two public builders:
    build_student_term_report(student, term, year) -> bytes
    build_class_term_report(class_group, term, year) -> bytes  (one PDF, page break per student)

Note on date filtering: marks are filtered by their stored term + academic_year. Attendance
and behavior notes don't store a term, so they are filtered by year only and labeled
"Year-to-date" on the report. Adding per-school term date ranges is a future improvement.
"""

from collections import defaultdict
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models import Attendance, BehaviorNote, Mark, TermSchedule

EMERALD = colors.HexColor("#047857")
EMERALD_LIGHT = colors.HexColor("#D1FAE5")
SLATE = colors.HexColor("#334155")
SLATE_LIGHT = colors.HexColor("#F1F5F9")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=18, textColor=EMERALD,
            spaceAfter=2, alignment=1,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontSize=10, textColor=SLATE,
            alignment=1, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=12, textColor=EMERALD,
            spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9, leading=12),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=8, textColor=SLATE),
    }


def _header_footer(canvas, doc):
    """Draw page footer (generated date + page number)."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SLATE)
    footer = f"Generated {datetime.now():%Y-%m-%d %H:%M}  |  Page {doc.page}"
    canvas.drawRightString(A4[0] - 1.5 * cm, 1 * cm, footer)
    canvas.drawString(1.5 * cm, 1 * cm, "ThutoTrack term report")
    canvas.restoreState()


def _school_header(school, styles):
    flow = []
    name = Paragraph(f"<b>{school.name}</b>", styles["title"])
    flow.append(name)

    bits = []
    if school.address:
        bits.append(school.address)
    if school.phone:
        bits.append(school.phone)
    if school.email:
        bits.append(school.email)
    if bits:
        flow.append(Paragraph(" &middot; ".join(bits), styles["subtitle"]))
    return flow


def _term_label(term: int) -> str:
    return f"Term {term}"


def _student_info_block(student, term, year, styles):
    flow = [
        Paragraph(f"<b>{_term_label(term)} Report &mdash; {year}</b>", styles["h2"]),
    ]
    info = [
        ["Student", student.full_name, "Student no.", student.student_number],
        ["Class", student.class_group.name, "Grade", str(student.class_group.grade_level)],
        ["Gender", student.get_gender_display() or "—", "Date of birth",
         student.date_of_birth.isoformat() if student.date_of_birth else "—"],
        ["Parent", student.parent_name or "—", "Parent phone", student.parent_phone or "—"],
    ]
    t = Table(info, colWidths=[2.8 * cm, 6.5 * cm, 2.8 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), SLATE),
        ("TEXTCOLOR", (2, 0), (2, -1), SLATE),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, -1), SLATE_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(t)
    return flow


def _marks_section(student, term, year, styles):
    flow = [Paragraph(f"Marks &mdash; {_term_label(term)} {year}", styles["h2"])]

    marks = (
        Mark.objects.filter(student=student, term=term, academic_year=year)
        .select_related("subject")
        .order_by("subject__name", "recorded_at")
    )
    if not marks:
        flow.append(Paragraph("No marks recorded for this term.", styles["body"]))
        return flow, None

    by_subject = defaultdict(list)
    for m in marks:
        by_subject[m.subject].append(m)

    rows = [["Subject", "Assessments", "Total score", "Out of", "Average %"]]
    overall_pcts = []
    for subject in sorted(by_subject, key=lambda s: s.name):
        ms = by_subject[subject]
        total_score = sum(float(m.score) for m in ms)
        total_max = sum(float(m.max_score) for m in ms)
        avg = (total_score / total_max * 100) if total_max else 0
        overall_pcts.append(avg)
        rows.append([
            subject.name,
            str(len(ms)),
            f"{total_score:g}",
            f"{total_max:g}",
            f"{avg:.1f}%",
        ])

    overall = sum(overall_pcts) / len(overall_pcts) if overall_pcts else 0
    rows.append(["Overall", "", "", "", f"{overall:.1f}%"])

    t = Table(rows, colWidths=[6 * cm, 2.5 * cm, 3 * cm, 2.5 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), EMERALD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BACKGROUND", (0, -1), (-1, -1), EMERALD_LIGHT),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, SLATE_LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(t)

    flow.append(Spacer(1, 4))
    flow.append(Paragraph("Detail by assessment:", styles["body"]))
    detail_rows = [["Subject", "Assessment", "Type", "Score", "Out of", "%"]]
    for subject in sorted(by_subject, key=lambda s: s.name):
        for m in by_subject[subject]:
            detail_rows.append([
                subject.name,
                m.title,
                m.get_assessment_type_display(),
                f"{m.score:g}",
                f"{m.max_score:g}",
                f"{m.percentage:.1f}%",
            ])
    dt = Table(detail_rows, colWidths=[3.5 * cm, 5 * cm, 2 * cm, 2 * cm, 2 * cm, 2.5 * cm])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SLATE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    flow.append(dt)

    return flow, overall


def _get_term_schedule(school, term: int, year: int):
    return TermSchedule.objects.filter(school=school, academic_year=year, term=term).first()


def _attendance_section(student, term, year, styles):
    schedule = _get_term_schedule(student.school, term, year)
    if schedule:
        label = (
            f"Attendance &mdash; Term {term} "
            f"({schedule.start_date:%d %b} &ndash; {schedule.end_date:%d %b} {year})"
        )
        qs = Attendance.objects.filter(
            student=student, date__gte=schedule.start_date, date__lte=schedule.end_date,
        )
    else:
        label = f"Attendance &mdash; Year-to-date {year} (no term dates configured)"
        qs = Attendance.objects.filter(student=student, date__year=year)

    flow = [Paragraph(label, styles["h2"])]
    counts = {label: 0 for _, label in Attendance.Status.choices}
    status_to_label = dict(Attendance.Status.choices)
    for a in qs:
        counts[status_to_label[a.status]] += 1
    total = sum(counts.values())
    present = counts.get("Present", 0)
    rate = (present / total * 100) if total else None

    rows = [["Present", "Absent", "Late", "Excused", "Total days", "Attendance rate"]]
    rows.append([
        str(counts.get("Present", 0)),
        str(counts.get("Absent", 0)),
        str(counts.get("Late", 0)),
        str(counts.get("Excused", 0)),
        str(total),
        f"{rate:.1f}%" if rate is not None else "—",
    ])
    t = Table(rows, colWidths=[2.8 * cm] * 5 + [3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), EMERALD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0, 1), (-1, 1), SLATE_LIGHT),
    ]))
    flow.append(t)
    return flow


def _behavior_section(student, term, year, styles):
    schedule = _get_term_schedule(student.school, term, year)
    if schedule:
        label = (
            f"Behavior notes &mdash; Term {term} "
            f"({schedule.start_date:%d %b} &ndash; {schedule.end_date:%d %b} {year})"
        )
        notes_qs = BehaviorNote.objects.filter(
            student=student,
            recorded_at__date__gte=schedule.start_date,
            recorded_at__date__lte=schedule.end_date,
        )
    else:
        label = f"Behavior notes &mdash; {year} (no term dates configured)"
        notes_qs = BehaviorNote.objects.filter(student=student, recorded_at__year=year)

    flow = [Paragraph(label, styles["h2"])]
    notes = notes_qs.select_related("teacher__user").order_by("-recorded_at")
    if not notes:
        flow.append(Paragraph("No behavior notes recorded.", styles["body"]))
        return flow

    rows = [["Date", "Category", "Teacher", "Note"]]
    for n in notes:
        rows.append([
            n.recorded_at.strftime("%Y-%m-%d"),
            n.get_category_display(),
            str(n.teacher.user),
            Paragraph(n.note, styles["body"]),
        ])
    t = Table(rows, colWidths=[2.2 * cm, 2 * cm, 3.5 * cm, 9.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SLATE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_LIGHT]),
    ]))
    flow.append(t)
    return flow


def _signature_block(student, styles):
    flow = [Spacer(1, 8)]
    class_teacher = student.class_group.class_teacher
    teacher_name = str(class_teacher.user) if class_teacher else "____________________"
    rows = [
        ["Class teacher:", teacher_name, "Signature:", ""],
        ["Principal:", "____________________", "Date:", ""],
        ["Parent acknowledgement:", "____________________", "Date:", ""],
    ]
    t = Table(rows, colWidths=[4 * cm, 5 * cm, 2.5 * cm, 5 * cm], rowHeights=[1 * cm] * 3)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("LINEBELOW", (1, 0), (1, -1), 0.5, colors.grey),
        ("LINEBELOW", (3, 0), (3, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    flow.append(t)
    return flow


def _student_story(student, term, year, styles):
    """Build the flowables for one student's report (no doc wrapper)."""
    story = []
    story.extend(_school_header(student.school, styles))
    story.extend(_student_info_block(student, term, year, styles))
    story.append(Spacer(1, 4))
    marks_flow, _ = _marks_section(student, term, year, styles)
    story.extend(marks_flow)
    story.append(Spacer(1, 4))
    story.extend(_attendance_section(student, term, year, styles))
    story.append(Spacer(1, 4))
    story.extend(_behavior_section(student, term, year, styles))
    story.extend(_signature_block(student, styles))
    return story


def build_student_term_report(student, term: int, year: int) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"{student.full_name} - Term {term} {year}",
        author="ThutoTrack",
    )
    styles = _styles()
    doc.build(_student_story(student, term, year, styles), onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def build_class_term_report(class_group, term: int, year: int) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"{class_group.name} - Term {term} {year}",
        author="ThutoTrack",
    )
    styles = _styles()
    story = []
    students = class_group.students.filter(is_active=True)
    for i, student in enumerate(students):
        if i > 0:
            story.append(PageBreak())
        story.extend(_student_story(student, term, year, styles))
    if not story:
        story = [Paragraph("No active students in this class.", styles["body"])]
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
