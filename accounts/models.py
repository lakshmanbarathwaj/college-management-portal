from django.conf import settings
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    class Role(models.TextChoices):
        STAFF = "staff", "Staff"
        STUDENT = "student", "Student"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    department = models.CharField(
        max_length=100,
        choices=(("B.Sc. Computer Science", "B.Sc. Computer Science"),),
        default="B.Sc. Computer Science",
    )
    phone = models.CharField(max_length=30, blank=True)
    expertise = models.CharField(max_length=300, blank=True)
    mentor = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="mentees",
        limit_choices_to={"role": Role.STAFF},
    )

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} ({self.get_role_display()})"


class Attendance(models.Model):
    student = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        limit_choices_to={"role": Profile.Role.STUDENT},
    )
    date = models.DateField(default=timezone.localdate)
    is_present = models.BooleanField(default=False)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marked_attendance",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date", "student__user__last_name")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "date"),
                name="unique_student_attendance_per_day",
            )
        ]

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student} — {self.date}: {status}"


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("due_date", "title")

    def __str__(self):
        return self.title


class AssignmentCompletion(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="completions",
    )
    student = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="assignment_completions",
        limit_choices_to={"role": Profile.Role.STUDENT},
    )
    is_completed = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_assignment_completions",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__user__last_name", "student__user__first_name")
        constraints = [
            models.UniqueConstraint(
                fields=("assignment", "student"),
                name="unique_assignment_completion_per_student",
            )
        ]

    def __str__(self):
        status = "Completed" if self.is_completed else "Not completed"
        return f"{self.assignment} — {self.student}: {status}"


class StudentMessage(models.Model):
    sender = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        limit_choices_to={"role": Profile.Role.STUDENT},
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ("is_read", "-sent_at")

    def __str__(self):
        return f"{self.subject} — {self.sender}"


class CourseResult(models.Model):
    subject = models.CharField(max_length=120, unique=True)
    pass_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_course_results",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("subject",)

    def __str__(self):
        return f"{self.subject}: {self.pass_percentage}% pass"


class StudentMark(models.Model):
    student = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="published_marks",
        limit_choices_to={"role": Profile.Role.STUDENT},
    )
    subject = models.CharField(max_length=120)
    mark = models.DecimalField(max_digits=5, decimal_places=2)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_student_marks",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "subject")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "subject"),
                name="unique_student_mark_per_subject",
            ),
            models.CheckConstraint(
                condition=models.Q(mark__gte=0, mark__lte=100),
                name="student_mark_between_0_and_100",
            ),
        ]

    def __str__(self):
        return f"{self.student} — {self.subject}: {self.mark}/100"


class ChatConversation(models.Model):
    student = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="chat_conversations",
        limit_choices_to={"role": Profile.Role.STUDENT},
    )
    human_handoff = models.BooleanField(default=False)
    forwarded_to = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="forwarded_chats",
        limit_choices_to={"role": Profile.Role.STAFF},
    )
    status = models.CharField(
        max_length=10,
        choices=(
            ("pending", "Pending"),
            ("replied", "Replied"),
            ("closed", "Closed"),
        ),
        default="pending",
    )
    forwarded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"Chat with {self.student}"


class ChatMessage(models.Model):
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="college_chat_messages",
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sent_at", "pk")

    def __str__(self):
        sender = self.sender.get_full_name() if self.sender else "Campus assistant"
        return f"{sender}: {self.body[:60]}"


class MembershipRequest(models.Model):
    class Role(models.TextChoices):
        STAFF = Profile.Role.STAFF, "Staff"
        STUDENT = Profile.Role.STUDENT, "Student"

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=Role.choices)
    department = models.CharField(
        max_length=100,
        choices=(("B.Sc. Computer Science", "B.Sc. Computer Science"),),
    )
    phone = models.CharField(max_length=30, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
