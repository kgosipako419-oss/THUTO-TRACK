"""Parent-facing views.

Two surfaces:
- WhatsApp webhook (``whatsapp_webhook``) — already used by Twilio.
- Web portal — login, dashboard, per-student view, PDF report download.

Parents are stored as ordinary ``User`` rows with ``role=PARENT`` and a
username equal to the normalized phone number (see
``core.whatsapp.normalize_phone_for_username``). Their PIN is the user's
password. PINs are managed by school admins, not the parent themselves.
"""

import base64
import hmac
from hashlib import sha1
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.models import Student, User
from core.reports import build_student_term_report
from core.whatsapp import (
    find_students_for_phone,
    handle_inbound,
    normalize_phone_for_username,
)


# ---------------------------------------------------------------------------
# WhatsApp webhook (Twilio compatible)
# ---------------------------------------------------------------------------

def _twilio_signature_valid(request) -> bool:
    token = getattr(settings, "WHATSAPP_AUTH_TOKEN", "") or ""
    if not token:
        return True
    sent = request.headers.get("X-Twilio-Signature", "")
    if not sent:
        return False
    url = request.build_absolute_uri(request.path)
    params = sorted(request.POST.items())
    payload = url + "".join(f"{k}{v}" for k, v in params)
    digest = hmac.new(token.encode("utf-8"), payload.encode("utf-8"), sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, sent)


def _twiml(text: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Response><Message>{escape(text)}</Message></Response>"
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == "GET":
        return HttpResponse(
            "ThutoTrack WhatsApp webhook is live. POST a message here.",
            content_type="text/plain",
        )
    if not _twilio_signature_valid(request):
        return HttpResponseForbidden("Invalid signature")
    from_field = request.POST.get("From", "")
    body = request.POST.get("Body", "")
    phone = from_field.replace("whatsapp:", "").strip()
    reply = handle_inbound(phone, body)
    return HttpResponse(_twiml(reply), content_type="application/xml; charset=utf-8")


# ---------------------------------------------------------------------------
# Parent web portal
# ---------------------------------------------------------------------------

def _parent_or_redirect(request):
    """Return the parent's accessible students, or None if not a parent user."""
    if not request.user.is_authenticated:
        return None
    if getattr(request.user, "role", "") != "PARENT":
        return None
    return find_students_for_phone(request.user.username)


def parent_login(request):
    if request.user.is_authenticated and getattr(request.user, "role", "") == "PARENT":
        return redirect("parents:dashboard")

    error = None
    phone_input = ""
    if request.method == "POST":
        phone_input = (request.POST.get("phone") or "").strip()
        pin = (request.POST.get("pin") or "").strip()
        username = normalize_phone_for_username(phone_input)
        if not username or not pin:
            error = "Enter your phone number and PIN."
        else:
            user = authenticate(request, username=username, password=pin)
            if user is None or getattr(user, "role", "") != "PARENT":
                error = "We couldn't find a parent account with that phone and PIN."
            else:
                login(request, user)
                return redirect("parents:dashboard")

    return render(
        request,
        "parents/login.html",
        {"error": error, "phone_input": phone_input},
    )


def parent_logout(request):
    logout(request)
    return redirect("/")


@login_required
def dashboard(request):
    students = _parent_or_redirect(request)
    if students is None:
        return redirect("parents:login")
    return render(
        request,
        "parents/dashboard.html",
        {"students": students, "parent_phone": request.user.username},
    )


@login_required
def student_detail(request, student_id: int):
    students = _parent_or_redirect(request)
    if students is None:
        return redirect("parents:login")
    student = next((s for s in students if s.id == student_id), None)
    if student is None:
        return render(
            request,
            "parents/not_allowed.html",
            {"phone": request.user.username},
            status=404,
        )

    from collections import defaultdict
    from datetime import date as _date
    from django.utils.timezone import now

    year = now().year
    marks_qs = student.marks.select_related("subject").order_by("subject__name", "-recorded_at")
    marks_by_subject = defaultdict(list)
    for m in marks_qs:
        marks_by_subject[m.subject].append(m)

    subject_averages = []
    for subject, marks in marks_by_subject.items():
        avg = sum(m.percentage for m in marks) / len(marks) if marks else 0
        subject_averages.append({"subject": subject, "average": avg, "count": len(marks)})
    subject_averages.sort(key=lambda r: r["subject"].name)

    att_qs = student.attendance_records.filter(date__year=year)
    att_counts = {"Present": 0, "Absent": 0, "Late": 0, "Excused": 0}
    label_for = {"P": "Present", "A": "Absent", "L": "Late", "E": "Excused"}
    for a in att_qs:
        att_counts[label_for[a.status]] += 1
    total = sum(att_counts.values())
    rate = (att_counts["Present"] / total * 100) if total else None

    behavior_notes = (
        student.behavior_notes.select_related("teacher__user").order_by("-recorded_at")[:20]
    )

    return render(
        request,
        "parents/student_detail.html",
        {
            "student": student,
            "marks_by_subject": dict(marks_by_subject),
            "subject_averages": subject_averages,
            "att_counts": att_counts,
            "att_total": total,
            "att_rate": rate,
            "behavior_notes": behavior_notes,
            "year": year,
        },
    )


@login_required
def student_report(request, student_id: int):
    students = _parent_or_redirect(request)
    if students is None:
        return redirect("parents:login")
    student = next((s for s in students if s.id == student_id), None)
    if student is None:
        return HttpResponseForbidden("Not authorized")

    from django.utils.timezone import now

    try:
        term = int(request.GET.get("term") or 1)
    except ValueError:
        term = 1
    if term not in (1, 2, 3):
        term = 1
    try:
        year = int(request.GET.get("year") or now().year)
    except ValueError:
        year = now().year

    pdf = build_student_term_report(student, term, year)
    safe = student.full_name.replace(" ", "_")
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{safe}_Term{term}_{year}.pdf"'
    return response
