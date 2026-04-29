from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Trip, Booking, TravelerNotification, AdminNotification

class Command(BaseCommand):
    help = 'Update trip statuses based on current date'

    def handle(self, *args, **options):
        today = timezone.now().date()
        self.stdout.write(f"Running trip status updates for {today}")
        
        # 1. Trips Starting Today/Recently (APPROVED -> ONGOING)
        # We check start_date <= today AND end_date >= today
        starting_trips = Trip.objects.filter(
            status='APPROVED',
            start_date__lte=today,
            end_date__gte=today
        )
        
        for trip in starting_trips:
            self.stdout.write(f"Marking trip {trip.id} as ONGOING")
            trip.status = 'ONGOING'
            trip.save()
            
            # Notify travelers
            self.notify_travelers(trip, 'TRIP_ONGOING', 'Your trip has started!', f"Your trip to {trip.destination} is now ongoing. Have a great time!")
            
            # Notify company
            self.notify_company(trip, 'TRIP_ONGOING', f"Trip Started: {trip.title}", f"The trip '{trip.title}' to {trip.destination} has officially started.")
            
            # Notify admin
            self.notify_admin('TRIP_ONGOING', f"Trip Started: {trip.title}", f"Trip '{trip.title}' (ID: {trip.id}) has started.")

        # 2. Trips Completed (ONGOING -> COMPLETED)
        # We check end_date < today
        finished_trips = Trip.objects.filter(
            status='ONGOING',
            end_date__lt=today
        )
        
        for trip in finished_trips:
            self.stdout.write(f"Marking trip {trip.id} as COMPLETED")
            trip.status = 'COMPLETED'
            trip.save()
            
            # Notify travelers
            self.notify_travelers(trip, 'TRIP_COMPLETED', 'Trip Completed', f"Your trip to {trip.destination} has ended. Please share your experience!")
            
            # Notify company
            self.notify_company(trip, 'TRIP_COMPLETED', f"Trip Completed: {trip.title}", f"The trip '{trip.title}' has been marked as completed.")
            
            # Notify admin
            self.notify_admin('TRIP_COMPLETED', f"Trip Completed: {trip.title}", f"Trip '{trip.title}' (ID: {trip.id}) has completed.")

        # 3. Mark APPROVED trips as EXPIRED if end_date has passed
        # We check end_date < today for APPROVED trips (that didn't start)
        expired_trips = Trip.objects.filter(
            status__in=['APPROVED', 'PAUSED'],
            end_date__lt=today
        )
        
        for trip in expired_trips:
            self.stdout.write(f"Marking trip {trip.id} as EXPIRED")
            trip.status = 'EXPIRED'
            trip.save()
            
            # Notify company
            self.notify_company(trip, 'TRIP_EXPIRED', f"Trip Expired: {trip.title}", f"The trip '{trip.title}' has expired and is no longer available.")

        # 4. Upcoming Trips (1 day before start)
        tomorrow = today + timezone.timedelta(days=1)
        upcoming_trips = Trip.objects.filter(
            status='APPROVED',
            start_date=tomorrow
        )
        
        for trip in upcoming_trips:
            # Check if we haven't already notified (optional check logic could be added here to prevent dupes)
            # For now, we assume this runs once a day
            self.stdout.write(f"Sending reminders for trip {trip.id} starting tomorrow")
            self.notify_travelers(trip, 'TRIP_STARTING_SOON', 'Trip Starting Tomorrow!', f"Get ready! Your trip to {trip.destination} starts tomorrow.")

        self.stdout.write(self.style.SUCCESS('Successfully updated trip statuses'))

    def notify_travelers(self, trip, type, title, message):
        bookings = Booking.objects.filter(trip=trip, status='CONFIRMED')
        notifications = []
        for booking in bookings:
            notifications.append(TravelerNotification(
                user=booking.traveler,
                trip=trip,
                booking=booking,
                type=type,
                title=title,
                message=message
            ))
        TravelerNotification.objects.bulk_create(notifications)
        self.stdout.write(f" - Notified {len(notifications)} travelers")

    def notify_company(self, trip, type, title, message):
        AdminNotification.objects.create(
            type=type,
            title=title,
            message=message,
            company=trip.company
        )
        self.stdout.write(f" - Notified company {trip.company.company_name}")

    def notify_admin(self, type, title, message):
        AdminNotification.objects.create(
            type=type,
            title=title,
            message=message,
            company=None # Admin notification
        )
