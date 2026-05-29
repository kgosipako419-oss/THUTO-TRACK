"""WhatsApp message handler — provider-agnostic.

The webhook view normalizes the inbound payload into (phone, body) and calls
``handle_inbound``; the returned string is sent back to the parent.

Default integration target is Twilio's WhatsApp sandbox (their webhook posts
form-encoded ``From=whatsapp:+267...`` and ``Body=...`` fields), but nothing in
this file is Twilio-specific.
"""

import re
from collections import defaultdict

from django.db.models import Max
from django.utils import timezone

from core.models import ParentSession, Student, TermSchedule

UNKNOWN_PARENT_REPLY = (
    "Welcome to ThutoTrack.\n\n"
    "Your phone number isn't linked to a student yet. Please ask the school "
    "to register your number under your child's profile, then try again."
)

GREETING_WORDS = {"", "menu", "hi", "hello", "dumela", "help", "start", "?"}
MARKS_WORDS = {"marks", "m", "1"}
ATTENDANCE_WORDS = {"attendance", "att", "a", "2"}
REPORT_WORDS = {"report", "r", "summary", "3"}
BEHAVIOR_WORDS = {"behavior", "behaviour", "b", "4"}


# ---------------------------------------------------------------------------
# Phone matching
# ---------------------------------------------------------------------------

def _digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def normalize_phone_for_username(raw: str) -> str:
    """Canonical username form for a parent's phone number.

    Strips formatting and prepends "267" to the last 8 digits, so that
    "+267 71 222 001", "26771222001", "071222001" and "71222001" all map to
    the same username "26771222001". Returns an empty string for unusable input.
    """
    digits = _digits_only(raw)
    if not digits:
        return ""
    return "267" + digits[-8:] if len(digits) >= 8 else digits


def phones_match(stored: str, incoming: str) -> bool:
    """Compare phone numbers loosely.

    Matches if both strings reduce to the same digits, or if their last 8 digits
    match (covers Botswana mobile numbers stored with or without +267).
    """
    a = _digits_only(stored)
    b = _digits_only(incoming)
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= 8 and len(b) >= 8 and a[-8:] == b[-8:]


def find_students_for_phone(phone: str):
    """Return active students whose parent_phone matches the incoming number.

    Stored parent_phone values can include spaces / dashes / country codes, so
    we can't use a direct DB filter. Instead we iterate active students with a
    non-empty parent_phone and compare digit-by-digit in Python.
    """
    if not phone:
        return []
    candidates = (
        Student.objects.filter(is_active=True)
        .exclude(parent_phone="")
        .select_related("class_group", "school")
        .order_by("first_name", "last_name")
    )
    return [s for s in candidates if phones_match(s.parent_phone, phone)]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle_inbound(phone: str, body: str) -> str:
    text = (body or "").strip()
    cmd = text.lower()

    students = find_students_for_phone(phone)
    if not students:
        return UNKNOWN_PARENT_REPLY

    session, _ = ParentSession.objects.get_or_create(phone=phone)
    session.message_count += 1

    # If the parent only has one student, latch onto them for the whole session
    # so any later command Just Works.
    if len(students) == 1 and session.selected_student_id != students[0].id:
        session.selected_student = students[0]

    # Numeric selection picks a student from the welcome menu when there are
    # multiple students. We do this BEFORE treating "1" as the marks shortcut.
    if cmd.isdigit() and len(students) > 1:
        idx = int(cmd) - 1
        if 0 <= idx < len(students):
            session.selected_student = students[idx]
            session.save()
            return _render_student_menu(students[idx])
        session.save()
        return "Sorry, that's not one of your students. Reply *menu* to start over."

    if cmd in GREETING_WORDS:
        session.save()
        return _render_welcome(students)

    # Resolve which student this command is about.
    current = session.selected_student if session.selected_student in students else None
    if current is None and len(students) == 1:
        current = students[0]
        session.selected_student = current

    if current is None:
        session.save()
        return _render_welcome(students) + "\n\nReply with a number first."

    session.save()

    if cmd in MARKS_WORDS:
        return _render_marks(current)
    if cmd in ATTENDANCE_WORDS:
        return _render_attendance(current)
    if cmd in REPORT_WORDS:
        return _render_report_summary(current)
    if cmd in BEHAVIOR_WORDS:
        return _render_behavior(current)

    return _render_student_menu(current, prefix="Sorry, I didn't understand that.\n\n")


# ---------------------------------------------------------------------------
# Response renderers
# ---------------------------------------------------------------------------

def _render_welcome(students):
    lines = ["*ThutoTrack*", "Welcome.", ""]
    if len(students) > 1:
        lines.append("Your students:")
        for i, s in enumerate(students, 1):
            lines.append(f"{i}. {s.full_name} - {s.class_group.name}")
        lines.append("")
        lines.append("Reply with a number to choose a student.")
    else:
        s = students[0]
        lines.extend([
            f"Student: *{s.full_name}* ({s.class_group.name})",
            "",
            "Reply with:",
            "  *marks*  - recent marks",
            "  *attendance* - attendance summary",
            "  *report* - term summary",
            "  *behavior* - behavior notes",
            "  *help* - this menu",
        ])
    return "\n".join(lines)


def _render_student_menu(student, prefix: str = ""):
    return (
        f"{prefix}*{student.full_name}* ({student.class_group.name})\n\n"
        "Reply with:\n"
        "  *marks*\n"
        "  *attendance*\n"
        "  *report*\n"
        "  *behavior*\n"
        "  *menu* - switch student"
    )


def _render_marks(student):
    year = timezone.now().year
    marks = (
        student.marks.filter(academic_year=year)
        .select_related("subject")
        .order_by("-recorded_at")[:10]
    )
    if not marks:
        return f"No marks recorded for {student.full_name} yet this year."
    lines = [f"*{student.full_name}* - recent marks ({year})"]
    for m in marks:
        lines.append(
            f"  {m.subject.name}: {m.title} - {m.score}/{m.max_score} ({m.percentage:.0f}%) [T{m.term}]"
        )
    lines.append("\nReply *report* for a term summary.")
    return "\n".join(lines)


def _render_attendance(student):
    year = timezone.now().year
    att = student.attendance_records.filter(date__year=year)
    total = att.count()
    if total == 0:
        return f"No attendance records yet for {student.full_name} this year."
    present = att.filter(status="P").count()
    absent = att.filter(status="A").count()
    late = att.filter(status="L").count()
    excused = att.filter(status="E").count()
    rate = present / total * 100
    return (
        f"*{student.full_name}* - attendance ({year})\n"
        f"Present: {present}/{total} ({rate:.0f}%)\n"
        f"Absent: {absent}  |  Late: {late}  |  Excused: {excused}"
    )


def _resolve_current_term(student, year: int):
    """Pick a term to report on.

    Prefers today's term (if a schedule covers today AND that term has marks).
    Otherwise falls back to the most recent term that has marks, so parents
    always see something useful instead of an empty-term message.
    """
    today = timezone.now().date()
    schedules = TermSchedule.objects.filter(school=student.school, academic_year=year)
    for ts in schedules:
        if ts.start_date <= today <= ts.end_date:
            if student.marks.filter(academic_year=year, term=ts.term).exists():
                return ts.term
            break
    latest = student.marks.filter(academic_year=year).aggregate(Max("term"))["term__max"]
    return latest


def _render_report_summary(student):
    year = timezone.now().year
    term = _resolve_current_term(student, year)
    if term is None:
        return f"No marks yet for {student.full_name} in {year}."

    marks = student.marks.filter(academic_year=year, term=term).select_related("subject")
    if not marks:
        return f"No marks yet for {student.full_name} in Term {term} {year}."

    by_subject = defaultdict(list)
    for m in marks:
        by_subject[m.subject.name].append(m)

    lines = [f"*{student.full_name}* - Term {term} {year}"]
    overall_pcts = []
    for subj in sorted(by_subject):
        items = by_subject[subj]
        total = sum(float(m.score) for m in items)
        out_of = sum(float(m.max_score) for m in items)
        pct = (total / out_of * 100) if out_of else 0
        overall_pcts.append(pct)
        s = "s" if len(items) > 1 else ""
        lines.append(f"  {subj}: {pct:.0f}% ({len(items)} test{s})")
    if overall_pcts:
        avg = sum(overall_pcts) / len(overall_pcts)
        lines.append(f"\n*Overall: {avg:.0f}%*")
    return "\n".join(lines)


def _render_behavior(student):
    year = timezone.now().year
    notes = (
        student.behavior_notes.filter(recorded_at__year=year)
        .select_related("teacher__user")
        .order_by("-recorded_at")[:5]
    )
    if not notes:
        return f"No behavior notes recorded for {student.full_name} this year."
    lines = [f"*{student.full_name}* - recent behavior"]
    for n in notes:
        snippet = n.note if len(n.note) <= 100 else (n.note[:97] + "...")
        lines.append(
            f"  [{n.get_category_display()}] {snippet} ({n.recorded_at:%Y-%m-%d})"
        )
    return "\n".join(lines)
