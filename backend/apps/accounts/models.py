from django.db import models
from django.contrib.auth.models import User
from apps.core.models import TimestampModel


class StaffProfile(TimestampModel):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="staff_profile"
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True
    )

    department = models.CharField(
        max_length=100,
        blank=True
    )


    def __str__(self):
        return self.user.username