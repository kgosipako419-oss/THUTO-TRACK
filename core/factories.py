"""Shared test fixtures / factory helpers.

Named ``factories.py`` (no ``test_`` prefix) so Django's test discovery
ignores it. Tests import functions from here.
"""

from datetime import date

from django.contrib.auth.hashers import make_password

from core.models import (
    ClassGroup,
    School,
    SchoolAdminProfile,
    Student,
    Subject,
    TeacherProfile,
    TermSchedule,
    User,
)
from core.whatsapp import normalize_phone_for_username


def make_school(name="Test School", code="TST-1", **kwargs) -> School:
    return School.objects.create(name=name, code=code, **kwargs)


def make_user(username, password="testpass123", role=User.Role.TEACHER, **kwargs) -> User:
    return User.objects.create(
        username=username,
        password=make_password(password),
        role=role,
        **kwargs,
    )


def make_teacher(school, username="teach", password="teachpass1",
                 first_name="Test", last_name="Teacher", **profile_kwargs) -> TeacherProfile:
    user = make_user(
        username, password=password, role=User.Role.TEACHER,
        first_name=first_name, last_name=last_name,
    )
    return TeacherProfile.objects.create(user=user, school=school, **profile_kwargs)


def make_school_admin(school, username="admin1", password="adminpass1",
                      first_name="School", last_name="Head") -> SchoolAdminProfile:
    user = make_user(
        username, password=password, role=User.Role.SCHOOL_ADMIN,
        first_name=first_name, last_name=last_name,
    )
    return SchoolAdminProfile.objects.create(user=user, school=school, title="Principal")


def make_subject(school, code="MATH", name="Mathematics") -> Subject:
    return Subject.objects.create(school=school, code=code, name=name)


def make_class(school, name="Form 1A", grade_level=8, academic_year=2026,
               class_teacher=None) -> ClassGroup:
    return ClassGroup.objects.create(
        school=school, name=name, grade_level=grade_level,
        academic_year=academic_year, class_teacher=class_teacher,
    )


def make_student(school, class_group, student_number="S-001",
                 first_name="First", last_name="Last", parent_phone="",
                 **kwargs) -> Student:
    return Student.objects.create(
        school=school, class_group=class_group,
        student_number=student_number, first_name=first_name, last_name=last_name,
        parent_phone=parent_phone, **kwargs,
    )


def make_term_schedule(school, term=1, year=2026,
                       start=None, end=None) -> TermSchedule:
    return TermSchedule.objects.create(
        school=school, term=term, academic_year=year,
        start_date=start or date(year, 1, 15),
        end_date=end or date(year, 4, 10),
    )


def make_parent_account(phone_raw="+267 71 222 001", pin="1234"):
    """Create a User row representing a parent with a PIN. Returns the User."""
    username = normalize_phone_for_username(phone_raw)
    user, _ = User.objects.get_or_create(
        username=username, defaults={"role": User.Role.PARENT, "phone": phone_raw},
    )
    user.role = User.Role.PARENT
    user.set_password(pin)
    user.save()
    return user
