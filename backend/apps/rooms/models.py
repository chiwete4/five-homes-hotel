from django.db import models
from apps.core.models import TimestampModel


class Amenity(TimestampModel):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
    


class RoomType(TimestampModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    bed_type = models.CharField(max_length=100)
    bathroom_count = models.PositiveIntegerField(default=1)
    amenities = models.ManyToManyField(Amenity, related_name='room_types', blank=True)
    featured = models.BooleanField(default=False)
    max_guests = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    


class RoomImage(TimestampModel):
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='room_images/')
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    
    def __str__(self):
        return f"Image for {self.room_type.name}"
    

    
class Room(TimestampModel):
    room_number = models.CharField(max_length=20, unique=True)
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name="rooms"
    )
    floor = models.CharField(max_length=50, blank=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.room_number} - {self.room_type.name}"
    
    