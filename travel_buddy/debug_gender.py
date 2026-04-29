import os
import django
import sys

# Add the project directory to the sys.path
sys.path.append(r'd:\LPP\Travel Buddy\Travel Buddy\Travel Buddy\travel_buddy')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_buddy.settings')
django.setup()

from app.models import Trip, Booking

try:
    trip_id = 3
    t = Trip.objects.get(id=trip_id)
    print(f"--- Debugging Trip {trip_id}: {t.title} ---")
    
    bookings = t.bookings.filter(status='CONFIRMED')
    print(f"Total Confirmed Bookings: {bookings.count()}")
    
    for b in bookings:
        user = b.traveler
        print(f"User: {user.username} (ID: {user.id})")
        print(f"  - Gender (Raw DB Value): '{user.gender}'")
        print(f"  - Gender Type: {type(user.gender)}")
        
        # Test the view logic simulation
        gender_key = user.gender.upper() if user.gender else 'OTHER'
        print(f"  - View Logic Calculates: {gender_key}")

except Trip.DoesNotExist:
    print(f"Trip {trip_id} not found.")
except Exception as e:
    print(f"Error: {e}")
