import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_buddy.settings')
django.setup()

from app.models import Trip
print(f"Total trips: {Trip.objects.count()}")
print(f"Approved trips: {Trip.objects.filter(status='APPROVED').count()}")
print(f"Ongoing trips: {Trip.objects.filter(status='ONGOING').count()}")
print(f"Statuses found: {list(Trip.objects.values_list('status', flat=True).distinct())}")
