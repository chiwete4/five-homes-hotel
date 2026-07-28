from django.contrib import admin

from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_reference',
                     'guest_name', 
                     'room_type',
                     'check_in_date', 
                     'check_out_date',
                     'status',)
                     
    
    list_filter = ('status',
                    'check_in_date', 
                    'check_out_date')
                    
    search_fields = ('booking_reference',
                      'guest_name',
                        'guest_email')
    
    
    date_hierarchy = 'check_in_date'
