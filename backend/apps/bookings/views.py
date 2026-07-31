from django.contrib import messages
from django.conf import settings
from django.http import Http404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BookingDeclineForm, GuestBookingForm, BookingStatusForm
from .models import Booking


def _grant_booking_access(request, booking_reference):
    """
    Mark this session as verified for a specific booking reference.
    Called once the guest has proven ownership (via the status-check
    form) or immediately after they create the booking themselves.
    """
    request.session[f"booking_access_{booking_reference}"] = True


def _has_booking_access(request, booking_reference):
    """True only if this session was previously granted access to this booking."""
    return request.session.get(f"booking_access_{booking_reference}", False)


def check_booking_status(request):
    booking = None

    if request.method == "POST":
        form = BookingStatusForm(request.POST)

        if form.is_valid():
            booking = (
                Booking.objects
                .select_related("room_type")
                .filter(
                    booking_reference=form.cleaned_data[
                        "booking_reference"
                    ],
                    guest_email__iexact=form.cleaned_data[
                        "guest_email"
                    ],
                )
                .first()
            )

            if booking is None:
                form.add_error(
                    None,
                    (
                        "No booking matched that reference and email "
                        "address. Please check the details and try again."
                    ),
                )
            else:
                _grant_booking_access(request, booking.booking_reference)

                return redirect(
                    "bookings:booking-summary",
                    booking_reference=booking.booking_reference,
                )
    else:
        form = BookingStatusForm()

    return render(
        request,
        "bookings/guest/check_booking_status.html",
        {"form": form},
    )


# the dashboard view for staff users
@login_required
@permission_required("bookings.view_booking", raise_exception=True)
def receptionist_dashboard(request):
    pending_bookings = (
        Booking.objects
        .filter(status=Booking.Status.PAID)
        .select_related("room_type")
        .order_by("check_in_date", "created_at")
    )

    recent_decisions = (
        Booking.objects
        .filter(
            status__in=[
                Booking.Status.CONFIRMED,
                Booking.Status.DECLINED,
            ],
            reviewed_by=request.user,
        )
        .select_related("room_type", "reviewed_by")
        .order_by("-reviewed_at")[:10]
    )

    context = {
        "pending_bookings": pending_bookings,
        "recent_decisions": recent_decisions,
    }

    return render(
        request,
        "bookings/receptionist/dashboard.html",
        context,
    )

# the view for staff users to see the details of a specific booking

@login_required
@permission_required("bookings.view_booking", raise_exception=True)
def receptionist_booking_detail(request, booking_reference):
    booking = get_object_or_404(
        Booking.objects.select_related(
            "room_type",
            "reviewed_by",
        ),
        booking_reference=booking_reference,
    )

    context = {
        "booking": booking,
        "decline_form": BookingDeclineForm(),
    }

    return render(
        request,
        "bookings/receptionist/booking_detail.html",
        context,
    )
# the view for staff users to accept a booking/ accept a booking request from a guest

@login_required
@permission_required("bookings.change_booking", raise_exception=True)
@require_POST
def accept_booking(request, booking_reference):
    try:
        with transaction.atomic():
            booking = (
                Booking.objects
                .select_for_update()
                .get(booking_reference=booking_reference)
            )

            booking.accept(request.user)

        messages.success(
            request,
            f"Booking {booking.booking_reference} was confirmed.",
        )

    except Booking.DoesNotExist:
        messages.error(
            request,
            "The requested booking could not be found.",
        )

        return redirect("bookings:receptionist-dashboard")

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "bookings:receptionist-booking-detail",
        booking_reference=booking_reference,
    )

# the view for staff users to decline a booking/ decline a booking request from a guest

@login_required
@permission_required("bookings.change_booking", raise_exception=True)
@require_POST
def decline_booking(request, booking_reference):
    form = BookingDeclineForm(request.POST)

    if not form.is_valid():
        booking = get_object_or_404(
            Booking.objects.select_related(
                "room_type",
                "reviewed_by",
            ),
            booking_reference=booking_reference,
        )

        return render(
            request,
            "bookings/receptionist/booking_detail.html",
            {
                "booking": booking,
                "decline_form": form,
            },
            status=400,
        )

    try:
        with transaction.atomic():
            booking = (
                Booking.objects
                .select_for_update()
                .get(booking_reference=booking_reference)
            )

            booking.decline(
                staff_user=request.user,
                reason=form.cleaned_data["reason"],
            )

        messages.success(
            request,
            (
                f"Booking {booking.booking_reference} was declined "
                "and marked as refund eligible."
            ),
        )

    except Booking.DoesNotExist:
        messages.error(
            request,
            "The requested booking could not be found.",
        )

        return redirect("bookings:receptionist-dashboard")

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "bookings:receptionist-booking-detail",
        booking_reference=booking_reference,
    )


def create_booking(request):
    if request.method == "POST":
        form = GuestBookingForm(request.POST)

        if form.is_valid():
            booking = form.save()

            # The guest just created this booking, so this session
            # is implicitly verified for it — no separate email/ref
            # check needed before they land on the summary page.
            _grant_booking_access(request, booking.booking_reference)

            return redirect(
                "bookings:booking-summary",
                booking_reference=booking.booking_reference,
            )
    else:
        form = GuestBookingForm()

    return render(
        request,
        "bookings/guest/booking_form.html",
        {"form": form},
    )


def booking_summary(request, booking_reference):
    booking = get_object_or_404(
        Booking.objects.select_related("room_type"),
        booking_reference=booking_reference,
    )

    # Guests may only view a booking's details after proving ownership,
    # either by just creating it or by passing the reference+email check.
    if not _has_booking_access(request, booking.booking_reference):
        return redirect("bookings:check-booking-status")

    return render(
        request,
        "bookings/guest/booking_summary.html",
        {"booking": booking},
    )


@require_POST
def demo_payment(request, booking_reference):
    if not settings.DEBUG:
        raise Http404

    try:
        with transaction.atomic():
            booking = (
                Booking.objects
                .select_for_update()
                .get(booking_reference=booking_reference)
            )

            if booking.status != Booking.Status.PAYMENT_PENDING:
                messages.error(
                    request,
                    "This booking is not awaiting payment.",
                )
            else:
                booking.status = Booking.Status.PAID
                booking.save()

                messages.success(
                    request,
                    "Demo payment completed. The booking is awaiting review.",
                )

    except Booking.DoesNotExist:
        raise Http404

    return redirect(
        "bookings:booking-summary",
        booking_reference=booking_reference,
    )