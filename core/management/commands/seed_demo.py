"""Seed a small demo dataset so the teacher portal can be tried end-to-end.

Usage:
    python manage.py seed_demo

Creates:
    - admin superuser (admin / admin123)
    - one school
    - one teacher (mr_kgosi / teacher123) linked to the school
    - subjects, one class, and a handful of students
"""

from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Attendance,
    BehaviorNote,
    ClassGroup,
    Mark,
    School,
    SchoolAdminProfile,
    Student,
    Subject,
    TeacherProfile,
    TermSchedule,
    User,
)


class Command(BaseCommand):
    help = "Create a small demo school, teacher, class and students for local testing."

    @transaction.atomic
    def handle(self, *args, **options):
        year = datetime.now().year

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "role": User.Role.SCHOOL_ADMIN,
                "first_name": "Site",
                "last_name": "Admin",
                "email": "admin@example.com",
            },
        )
        # Always set the password — makes the command idempotent so re-running
        # it (or running it on a partially-seeded DB) restores the documented
        # demo credentials instead of silently keeping a stale password.
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("admin123")
        admin.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Reset'} superuser: admin / admin123"
        ))

        # Create a non-superuser school admin for portal testing
        principal_user, created = User.objects.get_or_create(
            username="mma_pula",
            defaults={
                "first_name": "Pula",
                "last_name": "Mokgothu",
                "email": "principal@demoschool.example",
                "role": User.Role.SCHOOL_ADMIN,
                "phone": "+267 71 100 001",
            },
        )
        principal_user.role = User.Role.SCHOOL_ADMIN
        principal_user.set_password("admin123")
        principal_user.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Reset'} school admin: mma_pula / admin123"
        ))

        school, _ = School.objects.get_or_create(
            code="DEMO-001",
            defaults={
                "name": "Gaborone Demo Secondary School",
                "region": "South-East",
                "address": "Plot 1234, Gaborone",
                "phone": "+267 390 0000",
                "email": "info@demoschool.example",
                "principal_name": "Mma Kgomotso",
            },
        )

        SchoolAdminProfile.objects.get_or_create(
            user=principal_user,
            defaults={"school": school, "title": "Principal", "employee_id": "A-001"},
        )
        # Link the seeded superuser to the same school too
        SchoolAdminProfile.objects.get_or_create(
            user=admin, defaults={"school": school, "title": "System admin"},
        )

        # Default Botswana-style 3-term schedule for the current year
        term_dates = [
            (1, date(year, 1, 15), date(year, 4, 10)),
            (2, date(year, 5, 5), date(year, 8, 7)),
            (3, date(year, 9, 1), date(year, 12, 4)),
        ]
        for term_num, start, end in term_dates:
            TermSchedule.objects.get_or_create(
                school=school,
                academic_year=year,
                term=term_num,
                defaults={"start_date": start, "end_date": end},
            )

        subject_data = [
            ("Mathematics", "MATH"),
            ("English", "ENG"),
            ("Setswana", "SET"),
            ("Science", "SCI"),
            ("Social Studies", "SOC"),
        ]
        subjects = []
        for name, code in subject_data:
            subj, _ = Subject.objects.get_or_create(school=school, code=code, defaults={"name": name})
            subjects.append(subj)

        teacher_user, created = User.objects.get_or_create(
            username="mr_kgosi",
            defaults={
                "first_name": "Kgosi",
                "last_name": "Mokwena",
                "email": "kgosi@demoschool.example",
                "role": User.Role.TEACHER,
                "phone": "+267 71 000 001",
            },
        )
        teacher_user.role = User.Role.TEACHER
        teacher_user.set_password("teacher123")
        teacher_user.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Reset'} teacher: mr_kgosi / teacher123"
        ))

        teacher, _ = TeacherProfile.objects.get_or_create(
            user=teacher_user,
            defaults={"school": school, "employee_id": "T-001"},
        )
        teacher.subjects.set(subjects[:3])

        class_group, _ = ClassGroup.objects.get_or_create(
            school=school,
            name="Form 1A",
            academic_year=year,
            defaults={"grade_level": 8, "class_teacher": teacher},
        )
        teacher.classes_taught.add(class_group)

        student_data = [
            ("Naledi", "Seretse", "S-2026-001", "+267 71 222 001", "F"),
            ("Tumelo", "Khama", "S-2026-002", "+267 71 222 002", "M"),
            ("Lerato", "Molefe", "S-2026-003", "+267 71 222 003", "F"),
            ("Boitumelo", "Mogae", "S-2026-004", "+267 71 222 004", "F"),
            ("Tshepo", "Masire", "S-2026-005", "+267 71 222 005", "M"),
            ("Onkabetse", "Pula", "S-2026-006", "+267 71 222 006", "M"),
        ]
        for first, last, number, phone, gender in student_data:
            Student.objects.get_or_create(
                school=school,
                student_number=number,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "class_group": class_group,
                    "gender": gender,
                    "parent_name": f"{last} family",
                    "parent_phone": phone,
                },
            )

        # Seed sample marks, attendance and a behavior note for Naledi so that
        # the WhatsApp parent flow has something to reply with out of the box.
        naledi = Student.objects.filter(school=school, student_number="S-2026-001").first()
        if naledi:
            math = next((s for s in subjects if s.code == "MATH"), None)
            english = next((s for s in subjects if s.code == "ENG"), None)
            setswana = next((s for s in subjects if s.code == "SET"), None)
            sample_marks = [
                (math, "TEST", "Mid-term test 1", 78, 100),
                (math, "QUIZ", "Chapter 3 quiz", 18, 20),
                (english, "ASSIGN", "Essay: My village", 42, 50),
                (setswana, "TEST", "Reading comprehension", 65, 80),
            ]
            for subject, atype, title, score, max_score in sample_marks:
                if subject is None:
                    continue
                Mark.objects.get_or_create(
                    student=naledi, subject=subject, teacher=teacher,
                    title=title, term=1, academic_year=year,
                    defaults={"assessment_type": atype, "score": score, "max_score": max_score},
                )

            today = date.today()
            for delta, status in [(0, "P"), (1, "P"), (2, "A"), (3, "P"), (4, "L")]:
                Attendance.objects.get_or_create(
                    student=naledi, date=today - timedelta(days=delta),
                    defaults={"status": status, "recorded_by": teacher},
                )

            BehaviorNote.objects.get_or_create(
                student=naledi, teacher=teacher,
                note="Helped a classmate with their Setswana homework.",
                defaults={"category": "POS"},
            )

        # Seed a parent web account for Naledi's parent so the parent portal
        # demo works out of the box.
        from core.whatsapp import normalize_phone_for_username

        parent_phone_raw = "+267 71 222 001"
        parent_username = normalize_phone_for_username(parent_phone_raw)
        parent_user, _ = User.objects.get_or_create(
            username=parent_username,
            defaults={
                "first_name": "Seretse family",
                "role": User.Role.PARENT,
                "phone": parent_phone_raw,
            },
        )
        parent_user.role = User.Role.PARENT
        parent_user.set_password("1234")
        parent_user.save()

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("")
        self.stdout.write("Log in at / with:")
        self.stdout.write("    teacher portal:      mr_kgosi / teacher123")
        self.stdout.write("    school admin portal: mma_pula / admin123")
        self.stdout.write("    Django admin:        admin / admin123")
        self.stdout.write("    parent web portal:   +267 71 222 001 / 1234")
        self.stdout.write("")
        self.stdout.write("Parent WhatsApp demo: same phone, just message the webhook:")
        self.stdout.write("    POST /whatsapp/webhook/ From=whatsapp:+26771222001 Body=marks")
