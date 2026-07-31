from django.urls import path

from . import views


app_name = "bookings"


urlpatterns = [
    path(
    "new/",
    views.create_booking,
    name="create-booking",
    ),
    path(
    "status/",
    views.check_booking_status,
    name="check-booking-status",
),
    path(
        "<str:booking_reference>/summary/",
        views.booking_summary,
        name="booking-summary",
    ),
    path(
        "<str:booking_reference>/demo-payment/",
        views.demo_payment,
        name="demo-payment",
    ),
        path(
            "staff/reception/",
            views.receptionist_dashboard,
            name="receptionist-dashboard",
        ),
        path(
            "staff/reception/<str:booking_reference>/",
            views.receptionist_booking_detail,
            name="receptionist-booking-detail",
        ),
        path(
            "staff/reception/<str:booking_reference>/accept/",
            views.accept_booking,
            name="accept-booking",
        ),
        path(
            "staff/reception/<str:booking_reference>/decline/",
            views.decline_booking,
            name="decline-booking",
        ),
]