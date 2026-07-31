from django import forms
from datetime import date

from.models import Booking


class BookingDeclineForm(forms.Form):
    reason = forms.CharField(
        label="Reason for declining",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why the hotel cannot accommodate this booking."
                ),
            }
        ),
        max_length=1000,
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()

        if not reason:
            raise forms.ValidationError(
                "A decline reason is required."
            )

        return reason

class GuestBookingForm(forms.ModelForm):
    """
    Public-facing form guests use to submit a new booking request.
    Wraps Booking with extra cross-field validation (dates, capacity)
    that goes beyond what the model's own clean() checks.
    """

    class Meta:
        model = Booking   # Safe reference now that Booking is defined above
        fields = (
            "guest_name",
            "guest_email",
            "guest_phone",
            "room_type",
            "check_in_date",
            "check_out_date",
            "number_of_guests",
            "special_requests",
        )

        # ── Widget overrides: presentation hints for the rendered inputs ──
        widgets = {
            "guest_name": forms.TextInput(
                attrs={"placeholder": "Your full name"}
            ),
            "guest_email": forms.EmailInput(
                attrs={"placeholder": "you@example.com"}
            ),
            "guest_phone": forms.TextInput(
                attrs={"placeholder": "+234 800 000 0000"}
            ),
            "check_in_date": forms.DateInput(
                attrs={"type": "date"}   # Renders as a native HTML5 date picker
            ),
            "check_out_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "number_of_guests": forms.NumberInput(
                attrs={"min": 1}   # Client-side floor; server-side check still applied in clean()
            ),
            "special_requests": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Optional requests",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        """Restrict the room_type choices to active rooms, cheapest first."""
        super().__init__(*args, **kwargs)

        self.fields["room_type"].queryset = (
            self.fields["room_type"]
            .queryset
            .filter(is_active=True)              # Hide rooms taken out of service
            .order_by("price_per_night")          # Cheapest options shown first
        )

    def clean(self):
        """
        Form-level validation guests hit *before* the data ever reaches
        Booking.clean()/full_clean() — catches bad input early with
        friendly, field-targeted error messages.
        """
        cleaned_data = super().clean()

        check_in = cleaned_data.get("check_in_date")
        check_out = cleaned_data.get("check_out_date")
        room_type = cleaned_data.get("room_type")
        number_of_guests = cleaned_data.get("number_of_guests")

        # Rule 1: no booking a check-in date that's already passed
        if check_in and check_in < date.today():
            self.add_error(
                "check_in_date",
                "Check-in cannot be in the past.",
            )

        # Rule 2: stay must span at least one night, in the correct order
        if check_in and check_out and check_out <= check_in:
            self.add_error(
                "check_out_date",
                "Check-out must be after check-in.",
            )

        # Rule 3: guest count floor, mirrors the model's PositiveIntegerField intent
        if number_of_guests is not None and number_of_guests < 1:
            self.add_error(
                "number_of_guests",
                "At least one guest is required.",
            )

        # Rule 4: guest count must not exceed the selected room's capacity
        if (
            room_type
            and number_of_guests
            and number_of_guests > room_type.max_guests
        ):
            self.add_error(
                "number_of_guests",
                (
                    f"{room_type.name} accommodates a maximum of "
                    f"{room_type.max_guests} guests."
                ),
            )

        return cleaned_data

class BookingStatusForm(forms.Form):
    booking_reference = forms.CharField(
        max_length=30,
        label="Booking reference",
        widget=forms.TextInput(
            attrs={
                "placeholder": "FH-20260731-A1B2C3D4",
                "autocomplete": "off",
            }
        ),
    )

    guest_email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "The email used for your booking",
                "autocomplete": "email",
            }
        ),
    )

    def clean_booking_reference(self):
        return self.cleaned_data["booking_reference"].strip().upper()

    def clean_guest_email(self):
        return self.cleaned_data["guest_email"].strip().lower()