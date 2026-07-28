import secrets
from datetime import date

from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.models import TimestampModel
from apps.rooms.models import RoomType


def generate_booking_reference():
    today = date.today().strftime("%Y%m%d")
    random_string = secrets.token_hex(4).upper()
    return f"FH-{today}-{random_string}"


class Booking(TimestampModel):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        CONFIRMED = "CONFIRMED", "Confirmed"
        DECLINED = "DECLINED", "Declined"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"


    booking_reference = models.CharField(
        max_length=25,
        unique=True,
        editable=False
    )

    guest_name = models.CharField(max_length=150)

    guest_email = models.EmailField()

    guest_phone = PhoneNumberField(
        region="NG",
        blank=True,
        null=True
    )

    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name="bookings"
    )

    check_in_date = models.DateField()

    check_out_date = models.DateField()

    number_of_guests = models.PositiveIntegerField()

    special_requests = models.TextField(
        blank=True
    )


    decline_reason = models.TextField(
    blank=True,
    null=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )


    def save(self, *args, **kwargs):
        if not self.booking_reference:
            self.booking_reference = generate_booking_reference()

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.booking_reference} - {self.guest_name}"