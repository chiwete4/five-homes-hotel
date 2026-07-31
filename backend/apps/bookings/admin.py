from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "booking_reference",
        "guest_name",
        "room_type",
        "check_in_date",
        "check_out_date",
        "status",
        "refund_status",
    )

    list_filter = (
        "status",
        "refund_status",
        "check_in_date",
        "check_out_date",
    )

    search_fields = (
        "booking_reference",
        "guest_name",
        "guest_email",
    )

    readonly_fields = (
        "booking_reference",
        "guest_name",
        "guest_email",
        "guest_phone",
        "room_type",
        "check_in_date",
        "check_out_date",
        "number_of_guests",
        "special_requests",
        "decline_reason",
        "cancellation_reason",
        "reviewed_by",
        "reviewed_at",
        "cancelled_at",
        "refund_eligible_at_cancellation",
        "refund_initiated_at",
        "refunded_at",
        "refund_reference",
        "created_at",
        "updated_at",
    )

    date_hierarchy = "check_in_date"

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        # Receptionists process bookings only through their dashboard.
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser