from django.contrib import admin
from .models import Amenity, RoomType, RoomImage,Room


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_per_night",
        "max_guests",
        "featured",
        "is_active",
    )
    prepopulated_fields = {
        "slug": ("name",)
    }


@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = (
        "room_type",
        "is_primary",
        "display_order",
    )


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "room_number",
        "room_type",
        "floor",
        "is_available",
    )