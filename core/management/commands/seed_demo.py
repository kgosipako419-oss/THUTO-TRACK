"""Seed a small demo dataset so the teacher portal can be tried end-to-end.

Usage:
    python manage.py seed_demo

Creates:
    - admin superuser (admin / admin123)
    - one school
    - one teacher (mr_kgosi / teacher123) linked to the school
    - subjects, one class, and a handful of students
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import ClassGroup, School, Student, Subject, TeacherProfile, User


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
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(self.style.SUCCESS("Created superuser: admin / admin123"))
        else:
            self.stdout.write("Superuser 'admin' already exists, skipping.")

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
        if created:
            teacher_user.set_password("teacher123")
            teacher_user.save()
            self.stdout.write(self.style.SUCCESS("Created teacher user: mr_kgosi / teacher123"))

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

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("")
        self.stdout.write("Log in at /teachers/login/ with:")
        self.stdout.write("    teacher: mr_kgosi / teacher123")
        self.stdout.write("    admin (for /admin/): admin / admin123")
