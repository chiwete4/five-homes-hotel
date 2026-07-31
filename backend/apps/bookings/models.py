# ── Standard library ─────────────────────────────────────────────
import secrets                     # Cryptographically strong random tokens for booking refs
from datetime import date          # Used to stamp booking references + validate check-in dates

# ── Django core ───────────────────────────────────────────────────
from django.conf import settings                    # Access AUTH_USER_MODEL for FK relations
from django.core.exceptions import ValidationError   # Raised on invalid state transitions/data
from django.db import models                         # Base classes/fields for the ORM
from django.utils import timezone                     # Timezone-aware "now" for timestamps

# ── Third-party ───────────────────────────────────────────────────
from phonenumber_field.modelfields import PhoneNumberField  # Validated, region-aware phone field

# ── Local apps ────────────────────────────────────────────────────
from apps.core.models import TimestampModel   # Abstract base providing created_at/updated_at
from apps.rooms.models import RoomType        # FK target: the type of room being booked


def generate_booking_reference():
    """
    Build a human-readable, collision-resistant booking code.
    Format: FH-YYYYMMDD-XXXXXXXX (date + 8 hex chars of randomness).
    Called from Booking.save() only when no reference exists yet.
    """
    today = date.today().strftime("%Y%m%d")   # Date component: groups refs by creation day
    random_string = secrets.token_hex(4).upper()  # 4 random bytes -> 8 hex chars, uppercased
    return f"FH-{today}-{random_string}"       # Final assembled reference string


class Booking(TimestampModel):
    """
    Core reservation record: guest details, stay dates, lifecycle status,
    and cancellation/refund tracking, for a single room booking.
    """

    # ── Enum: overall lifecycle state of the booking ────────────────
    class Status(models.TextChoices):
        PAYMENT_PENDING = "PAYMENT_PENDING", "Payment pending"   # Created, payment not yet made
        PAYMENT_FAILED = "PAYMENT_FAILED", "Payment failed"      # Payment attempt was rejected
        PAID = "PAID", "Paid – awaiting review"                  # Paid, waiting on staff decision
        CONFIRMED = "CONFIRMED", "Confirmed"                     # Staff accepted the booking
        DECLINED = "DECLINED", "Declined"                        # Staff rejected the booking
        CANCELLED = "CANCELLED", "Cancelled"                     # Guest/staff cancelled after payment

    # ── Enum: refund lifecycle, independent of booking status ───────
    class RefundStatus(models.TextChoices):
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"  # Default; no refund scenario yet
        ELIGIBLE = "ELIGIBLE", "Eligible"                    # Guest qualifies for a refund
        NOT_ELIGIBLE = "NOT_ELIGIBLE", "Not eligible"        # Guest does not qualify
        PENDING = "PENDING", "Refund pending"                # Refund initiated, not completed
        REFUNDED = "REFUNDED", "Refunded"                    # Refund successfully completed
        FAILED = "FAILED", "Refund failed"                   # Refund attempt errored out

    # ── Identity field ───────────────────────────────────────────────
    booking_reference = models.CharField(
        max_length=25,
        unique=True,       # Enforces no duplicate booking codes at the DB level
        editable=False,    # Hidden from admin/forms; system-generated only
    )

    # ── Guest contact details ────────────────────────────────────────
    guest_name = models.CharField(
        max_length=150,     # Full name of the person the booking is under
    )

    guest_email = models.EmailField()   # Validated email; used for confirmations/notifications

    guest_phone = PhoneNumberField(
        region="NG",    # Assumes Nigerian numbers by default when no country code is given
        blank=True,     # Optional on forms
        null=True,      # Optional in DB (allows guests without a phone on file)
    )

    # ── Booking subject & dates ──────────────────────────────────────
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,        # Blocks deleting a RoomType that has existing bookings
        related_name="bookings",         # Enables room_type.bookings.all()
    )

    check_in_date = models.DateField()    # Stay start date
    check_out_date = models.DateField()   # Stay end date

    number_of_guests = models.PositiveIntegerField()   # Occupancy count; non-negative by design

    special_requests = models.TextField(
        blank=True,   # Free-text guest notes (e.g. late check-in); optional
    )

    # ── Lifecycle status ─────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PAYMENT_PENDING,   # Every new booking starts unpaid
    )

    # ── Decline audit trail ──────────────────────────────────────────
    decline_reason = models.TextField(
        blank=True,
        null=True,   # Only populated when status == DECLINED (enforced in clean())
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,          # Keep the booking record even if the staff account is deleted
        null=True,
        blank=True,
        related_name="reviewed_bookings",   # Enables user.reviewed_bookings.all()
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,   # Set the moment a staff member accepts/declines/cancels
    )

    # ── Cancellation audit trail ─────────────────────────────────────
    cancellation_reason = models.TextField(
        blank=True,   # Required in practice when status == CANCELLED (enforced in clean())
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,   # Timestamp set only when the booking transitions to CANCELLED
    )

    # ── Refund tracking ───────────────────────────────────────────────
    refund_status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.NOT_APPLICABLE,   # No refund scenario until decline/cancel happens
    )

    refund_eligible_at_cancellation = models.BooleanField(
        null=True,
        blank=True,   # Snapshot of eligibility rules at the moment of cancellation
    )

    refund_initiated_at = models.DateTimeField(
        null=True,
        blank=True,   # Set when staff/system starts processing the refund
    )

    refunded_at = models.DateTimeField(
        null=True,
        blank=True,   # Set when the refund actually completes
    )

    refund_reference = models.CharField(
        max_length=100,
        blank=True,   # External payment processor's refund transaction ID
    )

    # ── Derived/read-only state ──────────────────────────────────────
    @property
    def is_awaiting_review(self):
        """True only while the booking is paid and waiting on a staff decision."""
        return self.status == self.Status.PAID

    @property
    def number_of_nights(self):
        """Length of stay in nights; 0 if either date is missing."""
        if not self.check_in_date or not self.check_out_date:
            return 0

        return (self.check_out_date - self.check_in_date).days

    @property
    def total_amount(self):
        """
        Total price for the stay. Assumes RoomType has a
        `price_per_night` field; returns 0 if no room type is set.
        """
        if not self.room_type_id:
            return 0

        return self.room_type.price_per_night * self.number_of_nights

    # ── State transition: staff approves a paid booking ──────────────
    def accept(self, staff_user):
        """
        Move a PAID booking to CONFIRMED.
        Guards against accepting anything not currently awaiting review.
        """
        if self.status != self.Status.PAID:
            raise ValidationError(
                "Only paid bookings awaiting review can be accepted."
            )

        self.status = self.Status.CONFIRMED   # Booking is now locked in
        self.decline_reason = None            # Clear any stale decline reason
        self.reviewed_by = staff_user         # Audit: who made the decision
        self.reviewed_at = timezone.now()     # Audit: when the decision was made
        self.cancellation_reason = ""         # Clear any stale cancellation reason
        self.cancelled_at = None              # Audit: clear any stale cancellation info
        self.refund_status = self.RefundStatus.NOT_APPLICABLE  # No refund scenario for confirmed bookings

        self.save()   # Persists + triggers full_clean() via overridden save()

    # ── State transition: staff rejects a paid booking ────────────────
    def decline(self, staff_user, reason):
        """
        Move a PAID booking to DECLINED with a mandatory reason.
        Automatically marks the guest as refund-eligible since the
        hotel, not the guest, caused the cancellation.
        """
        reason = (reason or "").strip()   # Normalize whitespace before validation/storage

        if self.status != self.Status.PAID:
            raise ValidationError(
                "Only paid bookings awaiting review can be declined."
            )

        if not reason:
            raise ValidationError(
                "A reason is required when declining a booking."
            )

        self.status = self.Status.DECLINED
        self.decline_reason = reason
        self.reviewed_by = staff_user
        self.reviewed_at = timezone.now()

        # The hotel caused the cancellation, so the guest is eligible.
        self.refund_status = self.RefundStatus.ELIGIBLE

        self.save()

    # ── State transition: cancel an active booking ────────────────────
    def cancel(self, staff_user, reason):
        """
        Cancel a PAID or CONFIRMED booking with a mandatory reason.
        Marks refund-eligible by default; final refund approval is
        left to manual/management review.
        """
        reason = (reason or "").strip()   # Handles None safely, then normalizes whitespace

        if self.status not in [
            self.Status.PAID,
            self.Status.CONFIRMED,
        ]:
            raise ValidationError(
                "Only paid or confirmed bookings can be cancelled."
            )

        if not reason:
            raise ValidationError(
                "A reason is required when cancelling a booking."
            )

        self.status = self.Status.CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.reviewed_by = staff_user
        self.reviewed_at = timezone.now()
        self.decline_reason = None

        # Refunds remain a management/manual decision for now.
        self.refund_status = self.RefundStatus.ELIGIBLE

        self.save()

    # ── Cross-field validation, run on every save via full_clean() ────
    def clean(self):
        """
        Enforce consistency rules between `status` and its
        related reason fields that CharField/TextField choices
        alone can't express.
        """
        super().clean()   # Preserve any base-class validation from TimestampModel

        if self.check_in_date and self.check_in_date < date.today():
            raise ValidationError({
                "check_in_date": "Check-in date cannot be in the past."
            })
        if (
            self.check_in_date
            and self.check_out_date
            and self.check_out_date <= self.check_in_date
        ):
            raise ValidationError({
                "check_out_date": "Check-out must be after check-in."
            })
        if self.number_of_guests is not None and self.number_of_guests < 1:
            raise ValidationError({
                "number_of_guests": "At least one guest is required."
            })

        if (
            self.room_type_id
            and self.number_of_guests
            and self.number_of_guests > self.room_type.max_guests
        ):
            raise ValidationError({
                "number_of_guests": (
                    f"{self.room_type.name} accommodates a maximum of "
                    f"{self.room_type.max_guests} guests."
                )
            })

        decline_reason = (self.decline_reason or "").strip()
        cancellation_reason = (self.cancellation_reason or "").strip()

        # Rule 1: declining without a reason is not allowed
        if self.status == self.Status.DECLINED and not decline_reason:
            raise ValidationError({
                "decline_reason": "A reason is required when declining a booking."
            })

        # Rule 2: cancelling without a reason is not allowed
        if self.status == self.Status.CANCELLED and not cancellation_reason:
            raise ValidationError({
                "cancellation_reason": (
                    "A reason is required when cancelling a booking."
                )
            })

        # Rule 3: a decline reason should never linger on a non-declined booking
        if (
            self.status != self.Status.DECLINED
            and decline_reason
        ):
            raise ValidationError({
                "decline_reason": (
                    "A decline reason can only be stored on a declined booking."
                )
            })
        if (
            self.status != self.Status.CANCELLED
            and cancellation_reason
        ):
            raise ValidationError({
                "cancellation_reason": (
                    "A cancellation reason can only be stored on a cancelled booking."
                )
            })

    # ── Persistence hook: reference generation + forced validation ────
    def save(self, *args, **kwargs):
        """
        Assign a booking reference on first save, then always
        run full_clean() so model-level rules (see clean()) can't
        be bypassed by code that skips form validation.
        """
        if not self.booking_reference:
            self.booking_reference = generate_booking_reference()   # One-time, immutable assignment

        self.full_clean()             # Runs field validators + clean() above
        super().save(*args, **kwargs)  # Delegates to TimestampModel/Model.save for the actual write