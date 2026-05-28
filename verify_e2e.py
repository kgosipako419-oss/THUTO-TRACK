"""End-to-end verification of bulk upload + student profile.

Uses Django's test client (no live server needed). Exits non-zero on any failure.
"""

import os
import sys
from io import BytesIO

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thutotrack.settings")
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
django.setup()

from django.test import Client  # noqa: E402
from openpyxl import Workbook, load_workbook  # noqa: E402

from core.models import ClassGroup, Student  # noqa: E402

ASSERT_COUNT = 0


def check(label, cond, detail=""):
    global ASSERT_COUNT
    ASSERT_COUNT += 1
    if not cond:
        print(f"FAIL: {label}{(' — ' + detail) if detail else ''}")
        sys.exit(1)
    print(f"OK:   {label}")


def make_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["student_number", "first_name", "last_name", "gender", "date_of_birth", "parent_name", "parent_phone"])
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    buf.name = "sample.xlsx"
    return buf


c = Client()
assert c.login(username="mr_kgosi", password="teacher123"), "demo teacher login failed"

class_group = ClassGroup.objects.get(name="Form 1A")
class_url = f"/teachers/classes/{class_group.id}/"

# 1. Template download
resp = c.get(f"/teachers/classes/{class_group.id}/upload/template/")
check("template download 200", resp.status_code == 200, str(resp.status_code))
check(
    "template is xlsx",
    resp["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
content = b"".join(resp.streaming_content) if resp.streaming else resp.content
wb = load_workbook(BytesIO(content), read_only=True)
header = [c.value for c in next(wb.active.iter_rows(max_row=1))]
check("template header has student_number", "student_number" in header)
check("template header has parent_phone", "parent_phone" in header)

# 2. Upload form GET
resp = c.get(f"/teachers/classes/{class_group.id}/upload/")
check("upload form 200", resp.status_code == 200)
check("upload form shows download button", b"Download .xlsx template" in resp.content)

# 3. Upload with a bad row — expect rejection, no rows created
before = Student.objects.filter(class_group=class_group).count()
bad = make_xlsx([
    ["S-2026-101", "Mpho", "Tau", "F", "2011-04-12", "Mma Tau", "+267 71 333 001"],
    ["", "Bad", "Row", "", "", "", ""],
])
resp = c.post(f"/teachers/classes/{class_group.id}/upload/", {"file": bad})
check("bad upload returns 200 (form re-rendered)", resp.status_code == 200)
check("bad upload mentions rejection", b"Upload rejected" in resp.content)
check(
    "bad upload created NO students",
    Student.objects.filter(class_group=class_group).count() == before,
    f"before={before}, after={Student.objects.filter(class_group=class_group).count()}",
)

# 4. Upload with invalid gender — expect rejection
bad_gender = make_xlsx([
    ["S-2026-101", "Mpho", "Tau", "Z", "2011-04-12", "Mma Tau", "+267 71 333 001"],
])
resp = c.post(f"/teachers/classes/{class_group.id}/upload/", {"file": bad_gender})
check("invalid-gender upload rejected", b"Invalid gender" in resp.content)
check("still no students added", Student.objects.filter(class_group=class_group).count() == before)

# 5. Upload with duplicate student_number (one already seeded as S-2026-001) — should reject
dup = make_xlsx([
    ["S-2026-001", "Dup", "Student", "M", "", "", ""],
])
resp = c.post(f"/teachers/classes/{class_group.id}/upload/", {"file": dup})
check("duplicate student_number rejected", b"already exists" in resp.content)
check("still no students added", Student.objects.filter(class_group=class_group).count() == before)

# 6. Valid upload — students should be created and we redirect to class detail
good = make_xlsx([
    ["S-2026-101", "Mpho", "Tau", "F", "2011-04-12", "Mma Tau", "+267 71 333 001"],
    ["S-2026-102", "Kabo", "Sebina", "M", "2011-08-09", "Rra Sebina", "+267 71 333 002"],
])
resp = c.post(f"/teachers/classes/{class_group.id}/upload/", {"file": good}, follow=True)
check("good upload follows to class detail 200", resp.status_code == 200)
check("Mpho appears in class detail", b"Mpho Tau" in resp.content)
check("Kabo appears in class detail", b"Kabo Sebina" in resp.content)
check(
    "good upload created 2 new students",
    Student.objects.filter(class_group=class_group).count() == before + 2,
)

# 7. Student profile page
naledi = Student.objects.get(student_number="S-2026-001")
resp = c.get(f"/teachers/students/{naledi.id}/")
check("student profile 200", resp.status_code == 200)
check("profile shows name", b"Naledi Seretse" in resp.content)
check("profile shows attendance section", b"Recent attendance" in resp.content)
check("profile shows subject averages", b"Subject averages" in resp.content)
check("profile shows behavior section", b"Behavior notes" in resp.content)

# 8. Student profile for student outside teacher's class should 404
import core.models as core_models
other_school = core_models.School.objects.create(name="Other School", code="OTHER-1")
other_class = core_models.ClassGroup.objects.create(
    school=other_school, name="Other 1A", grade_level=8, academic_year=2026,
)
other_student = core_models.Student.objects.create(
    school=other_school, student_number="X-1", first_name="No", last_name="Access",
    class_group=other_class,
)
resp = c.get(f"/teachers/students/{other_student.id}/")
check("student outside teacher's class is 404", resp.status_code == 404)

# Clean up the other-school test fixtures so re-runs stay clean
other_student.delete()
other_class.delete()
other_school.delete()

# Clean up the students we just uploaded so the script is idempotent
Student.objects.filter(student_number__in=["S-2026-101", "S-2026-102"]).delete()

print(f"\nALL {ASSERT_COUNT} CHECKS PASSED")
