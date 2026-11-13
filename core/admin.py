from django.contrib import admin, messages
from django.contrib.auth.models import User

from .models import Certificate, Drive, HourLog, Profile, Signup


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "organization_name", "is_verified", "reports_to")
    list_filter = ("role", "is_verified")
    search_fields = ("user__username", "organization_name")
    actions = ["verify_organizers", "unverify_organizers"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "reports_to":
            kwargs["queryset"] = User.objects.filter(profile__role=Profile.ORGANIZER)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.action(description="Issue verified organizer credentials")
    def verify_organizers(self, request, queryset):
        updated = queryset.filter(role=Profile.ORGANIZER).update(is_verified=True)
        self.message_user(request, f"{updated} organizer(s) verified.", messages.SUCCESS)

    @admin.action(description="Revoke verified organizer credentials")
    def unverify_organizers(self, request, queryset):
        updated = queryset.filter(role=Profile.ORGANIZER).update(is_verified=False)
        self.message_user(request, f"{updated} organizer(s) un-verified.", messages.WARNING)


@admin.register(Drive)
class DriveAdmin(admin.ModelAdmin):
    list_display = ("title", "organizer", "date", "required_hours", "capacity", "is_open")
    list_filter = ("is_open", "date")
    search_fields = ("title", "location")


@admin.register(Signup)
class SignupAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "drive", "created_at")


@admin.register(HourLog)
class HourLogAdmin(admin.ModelAdmin):
    list_display = ("signup", "date", "hours", "status", "manager", "reviewed_at")
    list_filter = ("status",)


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("code", "signup", "total_hours", "issued_at")
    readonly_fields = ("code",)
