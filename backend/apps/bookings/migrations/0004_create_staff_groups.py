from django.db import migrations


def create_staff_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    receptionist, _ = Group.objects.get_or_create(
        name="Receptionist"
    )

    hotel_admin, _ = Group.objects.get_or_create(
        name="Hotel Admin"
    )

    # Receptionists can view and update bookings.
    receptionist_permissions = Permission.objects.filter(
        content_type__app_label="bookings",
        codename__in=[
            "view_booking",
            "change_booking",
        ],
    )

    receptionist.permissions.set(receptionist_permissions)

    # Hotel Admin receives all booking permissions.
    hotel_admin_permissions = Permission.objects.filter(
        content_type__app_label="bookings",
    )

    hotel_admin.permissions.set(hotel_admin_permissions)


def remove_staff_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")

    Group.objects.filter(
        name__in=[
            "Receptionist",
            "Hotel Admin",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0003_booking_decline_reason"),
    ]

    operations = [
        migrations.RunPython(
            create_staff_groups,
            remove_staff_groups,
        ),
    ]