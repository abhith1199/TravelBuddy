import os
import django
from django.db.models import Count, Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_buddy.settings')
django.setup()

from app.models import Trip, Booking, Login

def debug_insights():
    trip_id = 3
    print(f"Checking insights for Trip ID: {trip_id}")
    
    try:
        trip = Trip.objects.get(id=trip_id)
    except Trip.DoesNotExist:
        print("Trip not found.")
        return

    print(f"Trip: {trip.title}")
    print(f"Trip Current Bookings (field): {trip.current_bookings}")
    
    bookings = Booking.objects.filter(trip=trip, status='CONFIRMED')
    print(f"Confirmed Bookings (count): {bookings.count()}")
    
    total_people = bookings.aggregate(Sum('num_people'))['num_people__sum'] or 0
    print(f"Sum of num_people in bookings: {total_people}")
    
    # Check genders
    print("\nGender limit checks:")
    print(f"MALE count: {bookings.filter(traveler__gender='MALE').count()}")
    print(f"FEMALE count: {bookings.filter(traveler__gender='FEMALE').count()}")
    print(f"OTHER count: {bookings.filter(traveler__gender='OTHER').count()}")
    
    # Check actual values
    all_genders = list(bookings.values_list('traveler__gender', flat=True))
    print(f"\nActual gender values in bookings: {all_genders}")
    
    # Check all user genders
    all_user_genders = list(Login.objects.exclude(gender=None).exclude(gender='').values_list('gender', flat=True).distinct())
    print(f"Distinct genders in ALL Users: {all_user_genders}")

if __name__ == '__main__':
    debug_insights()
