import os
import django
import random
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_buddy.settings')
django.setup()

from app.models import Review, Booking, Trip, Login

def seed_reviews():
    print("Seeding reviews...")
    
    # Get confirmed bookings that don't have reviews
    # converting to list to avoid "query set changed size during iteration" if we were modifying
    bookings = list(Booking.objects.filter(status='CONFIRMED'))
    
    if not bookings:
        print("No confirmed bookings found. Please create some bookings first or update status of existing ones.")
        # Try to find some pending bookings and confirm them for testing
        pending_bookings = Booking.objects.filter(status='PENDING')[:5]
        for booking in pending_bookings:
            print(f"Confirming booking #{booking.id} for testing...")
            booking.status = 'CONFIRMED'
            booking.save()
            bookings.append(booking)
            
    if not bookings:
        print("Still no bookings. Creating a dummy booking...")
        # Try to find a traveler and a trip
        traveler = Login.objects.filter(usertype='traveler').first()
        trip = Trip.objects.first()
        
        if traveler and trip:
            booking = Booking.objects.create(
                traveler=traveler,
                trip=trip,
                status='CONFIRMED',
                num_people=1,
                total_price=trip.price
            )
            bookings.append(booking)
            print(f"Created dummy booking #{booking.id}")
        else:
            print("Could not find traveler or trip to create booking.")
            return

    count = 0
    for booking in bookings:
        # Check if review already exists
        if hasattr(booking, 'review'):
            continue
            
        print(f"Creating review for booking #{booking.id}...")
        
        Review.objects.create(
            trip=booking.trip,
            booking=booking,
            reviewer=booking.traveler,
            rating_overall=random.randint(3, 5),
            rating_social_vibe=random.randint(3, 5),
            rating_logistics=random.randint(3, 5),
            rating_safety=random.randint(4, 5),
            comment=random.choice([
                "Amazing trip! Had a blast.",
                "Well organized and fun.",
                "Great experience, would recommend.",
                "The guide was excellent.",
                "Beautiful locations but a bit tiring.",
                "Best trip ever!",
                "Everything was perfect."
            ]),
            created_at=timezone.now() - timedelta(days=random.randint(1, 10))
        )
        count += 1
        
    print(f"Successfully created {count} reviews.")

if __name__ == '__main__':
    seed_reviews()
