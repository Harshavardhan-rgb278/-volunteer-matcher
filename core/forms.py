from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Drive, HourLog, Profile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, initial=Profile.VOLUNTEER)
    organization_name = forms.CharField(
        max_length=150, required=False, help_text="Required for Non-Profit Admins (managers can leave it blank)."
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("role") == Profile.ORGANIZER and not cleaned.get("organization_name"):
            self.add_error("organization_name", "Please enter your organization name.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                role=self.cleaned_data["role"],
                organization_name=self.cleaned_data.get("organization_name", ""),
            )
        return user


class DriveForm(forms.ModelForm):
    class Meta:
        model = Drive
        fields = ["title", "description", "location", "date", "required_hours", "capacity", "is_open"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_capacity(self):
        capacity = self.cleaned_data["capacity"]
        if capacity < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        # Don't let an organizer shrink capacity below the volunteers already signed up.
        if self.instance.pk and capacity < self.instance.spots_taken:
            raise forms.ValidationError(
                f"{self.instance.spots_taken} volunteers have already signed up."
            )
        return capacity

    def clean_required_hours(self):
        hours = self.cleaned_data["required_hours"]
        if hours <= 0:
            raise forms.ValidationError("Required hours must be greater than 0.")
        return hours


class HourLogForm(forms.ModelForm):
    class Meta:
        model = HourLog
        fields = ["date", "hours", "description"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def clean_hours(self):
        hours = self.cleaned_data["hours"]
        if hours <= 0 or hours > 24:
            raise forms.ValidationError("Enter hours between 0.25 and 24.")
        return hours

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date > timezone.localdate():
            raise forms.ValidationError("You can't log hours for a future date.")
        return date
