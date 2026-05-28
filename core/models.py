from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SCHOOL_ADMIN = "ADMIN", "School Admin"
        TEACHER = "TEACHER", "Teacher"
        PARENT = "PARENT", "Parent"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.TEACHER)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class School(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Ministry / internal school code")
    region = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    principal_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Subject(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("school", "code"), name="unique_subject_code_per_school"),
        ]

    def __str__(self) -> str:
        return self.name


class ClassGroup(models.Model):
    """A class/form group, e.g. Form 1A, Standard 5B."""

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="class_groups")
    name = models.CharField(max_length=50, help_text="e.g. Form 1A, Standard 5B")
    grade_level = models.PositiveSmallIntegerField(help_text="Numeric grade/standard/form, e.g. 1-12")
    academic_year = models.PositiveSmallIntegerField()
    class_teacher = models.ForeignKey(
        "TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="form_classes",
    )

    class Meta:
        ordering = ("grade_level", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("school", "name", "academic_year"),
                name="unique_classgroup_per_school_year",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.academic_year})"


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher_profile")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="teachers")
    employee_id = models.CharField(max_length=30, blank=True)
    subjects = models.ManyToManyField(Subject, related_name="teachers", blank=True)
    classes_taught = models.ManyToManyField(ClassGroup, related_name="teachers", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("user__last_name", "user__first_name")

    def __str__(self) -> str:
        return f"{self.user} ({self.school.name})"


class SchoolAdminProfile(models.Model):
    """A school admin / HR user, with optional title."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="school_admin_profile")
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="admins")
    title = models.CharField(max_length=100, blank=True, help_text="e.g. 'Deputy Head', 'HR Manager'")
    employee_id = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ("user__last_name", "user__first_name")

    def __str__(self) -> str:
        return f"{self.user} ({self.school.name})"


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="students")
    student_number = models.CharField(max_length=30)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.PROTECT,
        related_name="students",
    )
    parent_name = models.CharField(max_length=200, blank=True)
    parent_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Used for parent USSD/WhatsApp lookup",
    )
    is_active = models.BooleanField(default=True)
    enrolled_at = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ("last_name", "first_name")
        constraints = [
            models.UniqueConstraint(
                fields=("school", "student_number"),
                name="unique_student_number_per_school",
            ),
        ]
        indexes = [
            models.Index(fields=("parent_phone",)),
        ]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.student_number})"


class Term(models.IntegerChoices):
    TERM_1 = 1, "Term 1"
    TERM_2 = 2, "Term 2"
    TERM_3 = 3, "Term 3"


class TermSchedule(models.Model):
    """Per-school date range for a term in a given academic year.

    Used to scope attendance and behavior notes when generating term reports.
    """

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="term_schedules")
    academic_year = models.PositiveSmallIntegerField()
    term = models.PositiveSmallIntegerField(choices=Term.choices)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ("academic_year", "term")
        constraints = [
            models.UniqueConstraint(
                fields=("school", "academic_year", "term"),
                name="unique_term_per_school_year",
            ),
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="term_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.school.name} — Term {self.term} {self.academic_year}"


class Enquiry(models.Model):
    """A message a teacher sends to school admin / HR. Admin handles via Django admin."""

    class Category(models.TextChoices):
        HR = "HR", "HR"
        ADMIN = "ADMIN", "Administration"
        TECH = "TECH", "Technical / ThutoTrack"
        ACADEMIC = "ACAD", "Academic"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "PROG", "In progress"
        RESOLVED = "DONE", "Resolved"

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="enquiries")
    from_teacher = models.ForeignKey(
        TeacherProfile, on_delete=models.CASCADE, related_name="enquiries",
    )
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.OTHER)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    response = models.TextField(blank=True, help_text="Filled in by admin/HR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name_plural = "Enquiries"
        indexes = [
            models.Index(fields=("school", "status")),
        ]

    def __str__(self) -> str:
        return f"[{self.get_status_display()}] {self.subject}"


class Mark(models.Model):
    class AssessmentType(models.TextChoices):
        TEST = "TEST", "Test"
        EXAM = "EXAM", "Exam"
        ASSIGNMENT = "ASSIGN", "Assignment"
        QUIZ = "QUIZ", "Quiz"
        PROJECT = "PROJ", "Project"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="marks")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="marks")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.PROTECT, related_name="marks_recorded")
    assessment_type = models.CharField(max_length=10, choices=AssessmentType.choices)
    title = models.CharField(max_length=200, help_text="e.g. 'Mid-term test 1', 'Chapter 3 quiz'")
    score = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(1)],
    )
    term = models.PositiveSmallIntegerField(choices=Term.choices)
    academic_year = models.PositiveSmallIntegerField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [
            models.Index(fields=("student", "academic_year", "term")),
            models.Index(fields=("subject", "academic_year", "term")),
        ]

    @property
    def percentage(self) -> float:
        return float(self.score) / float(self.max_score) * 100 if self.max_score else 0.0

    def __str__(self) -> str:
        return f"{self.student} - {self.subject} - {self.title}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "P", "Present"
        ABSENT = "A", "Absent"
        LATE = "L", "Late"
        EXCUSED = "E", "Excused"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=1, choices=Status.choices)
    recorded_by = models.ForeignKey(TeacherProfile, on_delete=models.PROTECT, related_name="attendance_recorded")
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(fields=("student", "date"), name="unique_attendance_per_student_per_day"),
        ]
        indexes = [
            models.Index(fields=("student", "date")),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.date} - {self.get_status_display()}"


class BehaviorNote(models.Model):
    class Category(models.TextChoices):
        POSITIVE = "POS", "Positive"
        NEUTRAL = "NEU", "Neutral"
        CONCERN = "CON", "Concern"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="behavior_notes")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.PROTECT, related_name="behavior_notes")
    category = models.CharField(max_length=3, choices=Category.choices, default=Category.NEUTRAL)
    note = models.TextField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)

    def __str__(self) -> str:
        return f"{self.student} - {self.get_category_display()} ({self.recorded_at:%Y-%m-%d})"
