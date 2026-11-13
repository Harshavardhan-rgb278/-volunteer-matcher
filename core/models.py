import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Profile(models.Model):
    """Role-based core: every user is either a Volunteer or a Non-Profit Admin."""

    VOLUNTEER = "volunteer"
    ORGANIZER = "organizer"
    MANAGER = "manager"
    ROLE_CHOICES = [
        (VOLUNTEER, "Resident / Volunteer"),
        (MANAGER, "Manager"),
        (ORGANIZER, "Non-Profit Admin"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=VOLUNTEER)
    organization_name = models.CharField(max_length=150, blank=True)
    # "Issue verified organizer credentials": a site superuser flips this in the admin panel.
    is_verified = models.BooleanField(default=False, help_text="Verified organizers can publish drives and sign certificates.")
    # Managers sit between volunteers and the admin. The site owner assigns which organizer a manager works for.
    reports_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="managers", help_text="For managers: the Non-Profit Admin this manager works for.",
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_organizer(self):
        return self.role == self.ORGANIZER

    @property
    def is_volunteer(self):
        return self.role == self.VOLUNTEER

    @property
    def is_manager(self):
        return self.role == self.MANAGER


class Drive(models.Model):
    """A volunteer drive posting with an hour requirement and a capacity cap."""

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="drives")
    title = models.CharField(max_length=150)
    description = models.TextField()
    location = models.CharField(max_length=200)
    date = models.DateField()
    required_hours = models.DecimalField(max_digits=5, decimal_places=2, help_text="Verified hours needed to earn a certificate.")
    capacity = models.PositiveIntegerField(help_text="Maximum number of volunteers.")
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "title"]

    def __str__(self):
        return self.title

    @property
    def spots_taken(self):
        return self.signups.count()

    @property
    def spots_left(self):
        return max(self.capacity - self.spots_taken, 0)

    @property
    def is_full(self):
        return self.spots_taken >= self.capacity


class Signup(models.Model):
    volunteer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signups")
    drive = models.ForeignKey(Drive, on_delete=models.CASCADE, related_name="signups")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("volunteer", "drive")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.volunteer} -> {self.drive}"

    def _sum(self, status):
        total = self.logs.filter(status=status).aggregate(t=Sum("hours"))["t"]
        return total or Decimal("0")

    @property
    def approved_hours(self):
        return self._sum(HourLog.APPROVED)

    @property
    def pending_hours(self):
        return self._sum(HourLog.PENDING)

    @property
    def manager_approved_hours(self):
        return self._sum(HourLog.MANAGER_APPROVED)

    @property
    def requirement_met(self):
        return self.approved_hours >= self.drive.required_hours

    @property
    def progress_percent(self):
        if not self.drive.required_hours:
            return 100
        return int(min(self.approved_hours / self.drive.required_hours, 1) * 100)


class HourLog(models.Model):
    """Automated hour tracker entry: logged by the volunteer, verified by the admin."""

    # Two-step approval: volunteer -> manager -> admin
    PENDING = "pending"                    # waiting for the manager
    MANAGER_APPROVED = "manager_approved"  # manager checked it, waiting for the admin
    APPROVED = "approved"                  # admin signed off (counts toward certificate)
    REJECTED = "rejected"
    STATUS_CHOICES = [
        (PENDING, "Awaiting manager"),
        (MANAGER_APPROVED, "Awaiting admin"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    signup = models.ForeignKey(Signup, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField()
    hours = models.DecimalField(max_digits=4, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    # manager step
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="manager_reviews"
    )
    manager_note = models.CharField(max_length=255, blank=True)
    manager_reviewed_at = models.DateTimeField(null=True, blank=True)
    # admin (organizer) step
    reviewer_note = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.hours}h on {self.date} ({self.status})"

    def manager_review(self, manager, approve, note=""):
        """Step 1: the manager checks the volunteer's activity and forwards it to the admin (or rejects it)."""
        self.status = self.MANAGER_APPROVED if approve else self.REJECTED
        self.manager = manager
        self.manager_note = note
        self.manager_reviewed_at = timezone.now()
        self.save()

    def review(self, approve, note=""):
        """Step 2: the admin (organizer) gives the final approval or rejection."""
        self.status = self.APPROVED if approve else self.REJECTED
        self.reviewer_note = note
        self.reviewed_at = timezone.now()
        self.save()
        if approve:
            Certificate.issue_if_eligible(self.signup)


class Certificate(models.Model):
    """Issued automatically once approved hours reach the drive requirement."""

    signup = models.OneToOneField(Signup, on_delete=models.CASCADE, related_name="certificate")
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    total_hours = models.DecimalField(max_digits=6, decimal_places=2)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate {self.code}"

    @classmethod
    def issue_if_eligible(cls, signup):
        if cls.objects.filter(signup=signup).exists() or not signup.requirement_met:
            return None
        organizer_profile = signup.drive.organizer.profile
        if not organizer_profile.is_verified:
            return None
        return cls.objects.create(signup=signup, total_hours=signup.approved_hours)
