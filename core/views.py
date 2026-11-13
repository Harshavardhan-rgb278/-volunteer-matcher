from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .certificates import build_certificate_pdf
from .decorators import manager_required, organizer_required, volunteer_required
from .forms import DriveForm, HourLogForm, RegisterForm
from .models import Certificate, Drive, HourLog, Profile, Signup


# ---------- Public / auth ----------

def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome! Your account has been created.")
        return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


def drive_list(request):
    """Browse local drive postings (open and upcoming)."""
    drives = Drive.objects.filter(is_open=True, date__gte=timezone.localdate()).select_related("organizer__profile")
    q = request.GET.get("q", "").strip()
    if q:
        drives = drives.filter(Q(title__icontains=q) | Q(location__icontains=q) | Q(description__icontains=q))
    return render(request, "core/drive_list.html", {"drives": drives, "q": q})


def drive_detail(request, pk):
    drive = get_object_or_404(Drive.objects.select_related("organizer__profile"), pk=pk)
    signup = None
    if request.user.is_authenticated:
        signup = Signup.objects.filter(volunteer=request.user, drive=drive).first()
    return render(request, "core/drive_detail.html", {"drive": drive, "signup": signup})


def certificate_verify(request, code):
    """Public page so anyone can confirm a certificate's authenticity."""
    certificate = Certificate.objects.select_related(
        "signup__volunteer", "signup__drive__organizer__profile"
    ).filter(code=code).first()
    return render(request, "core/certificate_verify.html", {"certificate": certificate})


# ---------- Routing ----------

@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    if profile is None:
        # e.g. a superuser created with createsuperuser has no Profile
        return redirect("admin:index") if request.user.is_staff else redirect("drive_list")
    if profile.is_organizer:
        return redirect("organizer_dashboard")
    if profile.is_manager:
        return redirect("manager_dashboard")
    return redirect("volunteer_dashboard")


# ---------- Volunteer portal ----------

@require_POST
@volunteer_required
def drive_signup(request, pk):
    # Lock the drive row so two volunteers can't take the last spot at once (capacity cap).
    with transaction.atomic():
        drive = Drive.objects.select_for_update().get(pk=pk)
        if not drive.is_open:
            messages.error(request, "This drive is closed.")
        elif Signup.objects.filter(volunteer=request.user, drive=drive).exists():
            messages.info(request, "You're already signed up for this drive.")
        elif drive.is_full:
            messages.error(request, "Sorry, this drive has reached its volunteer cap.")
        else:
            Signup.objects.create(volunteer=request.user, drive=drive)
            messages.success(request, f"You're signed up for {drive.title}!")
    return redirect("drive_detail", pk=pk)


@volunteer_required
def volunteer_dashboard(request):
    signups = (
        Signup.objects.filter(volunteer=request.user)
        .select_related("drive__organizer__profile")
        .prefetch_related("logs")
    )
    total_approved = sum(s.approved_hours for s in signups)
    return render(request, "core/volunteer_dashboard.html", {"signups": signups, "total_approved": total_approved})


@volunteer_required
def log_hours(request, signup_id):
    signup = get_object_or_404(Signup.objects.select_related("drive"), pk=signup_id, volunteer=request.user)
    form = HourLogForm(request.POST or None, initial={"date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        log = form.save(commit=False)
        log.signup = signup
        log.save()
        messages.success(request, "Hours submitted for admin review.")
        return redirect("volunteer_dashboard")
    return render(request, "core/log_hours.html", {"form": form, "signup": signup})


@login_required
def certificate_download(request, signup_id):
    signup = get_object_or_404(Signup.objects.select_related("drive", "volunteer"), pk=signup_id)
    allowed = request.user in (signup.volunteer, signup.drive.organizer) or request.user.is_superuser
    if not allowed:
        messages.error(request, "You can't access that certificate.")
        return redirect("dashboard")
    certificate = Certificate.objects.filter(signup=signup).first()
    if certificate is None:
        messages.error(request, "No certificate has been issued yet.")
        return redirect("dashboard")
    pdf = build_certificate_pdf(certificate)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="certificate-{certificate.code}.pdf"'
    return response


# ---------- Non-profit admin portal ----------

@organizer_required
def organizer_dashboard(request):
    drives = Drive.objects.filter(organizer=request.user).prefetch_related("signups")
    pending_count = organizer_queue(request.user).count()
    return render(
        request,
        "core/organizer_dashboard.html",
        {"drives": drives, "pending_count": pending_count, "verified": request.user.profile.is_verified},
    )


@organizer_required
def drive_create(request):
    if not request.user.profile.is_verified:
        messages.error(request, "Your organization must be verified before you can publish drives.")
        return redirect("organizer_dashboard")
    form = DriveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        drive = form.save(commit=False)
        drive.organizer = request.user
        drive.save()
        messages.success(request, "Drive published.")
        return redirect("organizer_dashboard")
    return render(request, "core/drive_form.html", {"form": form, "title": "Publish a new drive"})


@organizer_required
def drive_edit(request, pk):
    drive = get_object_or_404(Drive, pk=pk, organizer=request.user)
    form = DriveForm(request.POST or None, instance=drive)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Drive updated.")
        return redirect("organizer_dashboard")
    return render(request, "core/drive_form.html", {"form": form, "title": f"Edit: {drive.title}"})


def organizer_queue(organizer):
    """Logs the admin should look at.

    Normally only logs the manager already approved. If the organization has no manager yet,
    the admin reviews volunteer logs directly so nothing gets stuck.
    """
    logs = HourLog.objects.filter(signup__drive__organizer=organizer)
    if Profile.objects.filter(role=Profile.MANAGER, reports_to=organizer).exists():
        return logs.filter(status=HourLog.MANAGER_APPROVED)
    return logs.filter(status__in=[HourLog.PENDING, HourLog.MANAGER_APPROVED])


@organizer_required
def review_logs(request):
    logs = (
        organizer_queue(request.user)
        .select_related("signup__volunteer", "signup__drive", "manager")
        .order_by("date")
    )
    return render(request, "core/review_logs.html", {"logs": logs})


@require_POST
@organizer_required
def review_log_action(request, pk, action):
    log = get_object_or_404(organizer_queue(request.user), pk=pk)
    if action not in ("approve", "reject"):
        messages.error(request, "Unknown action.")
        return redirect("review_logs")
    note = request.POST.get("note", "").strip()[:255]
    with transaction.atomic():
        log.review(approve=(action == "approve"), note=note)
    if action == "approve":
        if Certificate.objects.filter(signup=log.signup).exists():
            messages.success(request, "Hours approved. Certificate issued to the volunteer.")
        else:
            messages.success(request, "Hours approved.")
    else:
        messages.warning(request, "Hours rejected.")
    return redirect("review_logs")


# ---------- Manager portal (step 1 of approval) ----------

def _manager_organizer(user):
    return user.profile.reports_to


@manager_required
def manager_dashboard(request):
    organizer = _manager_organizer(request.user)
    context = {"organizer": organizer, "logs": [], "volunteers": []}
    if organizer:
        context["logs"] = (
            HourLog.objects.filter(signup__drive__organizer=organizer, status=HourLog.PENDING)
            .select_related("signup__volunteer", "signup__drive")
            .order_by("date")
        )
        context["volunteers"] = (
            Signup.objects.filter(drive__organizer=organizer)
            .select_related("volunteer", "drive")
            .prefetch_related("logs")
        )
        context["reviewed_count"] = HourLog.objects.filter(manager=request.user).count()
    return render(request, "core/manager_dashboard.html", context)


@require_POST
@manager_required
def manager_review_action(request, pk, action):
    organizer = _manager_organizer(request.user)
    if organizer is None:
        messages.error(request, "You have not been assigned to an organization yet.")
        return redirect("manager_dashboard")
    log = get_object_or_404(
        HourLog, pk=pk, signup__drive__organizer=organizer, status=HourLog.PENDING
    )
    if action not in ("approve", "reject"):
        messages.error(request, "Unknown action.")
        return redirect("manager_dashboard")
    note = request.POST.get("note", "").strip()[:255]
    log.manager_review(manager=request.user, approve=(action == "approve"), note=note)
    if action == "approve":
        messages.success(request, "Checked and sent to the admin for final approval.")
    else:
        messages.warning(request, "Hours rejected.")
    return redirect("manager_dashboard")
