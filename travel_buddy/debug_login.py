import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_buddy.settings')
django.setup()

from app.models import Login
from django.contrib.auth import authenticate

def check_users():
    print("Checking users in database...")
    users = Login.objects.all()
    if not users:
        print("No users found!")
        return

    for user in users:
        print(f"User: {user.username}, Email: {user.email}, Is Active: {user.is_active}, Usertype: {user.usertype}")
        if user.view_password:
             print(f"   Stored view_password: {user.view_password}")
        else:
             print("   No view_password stored (expected for old users)")

    print("\n--- Testing Authentication ---")
    # Try to authenticate with a known test user if possible, or just print instructions
    print("If you know a password for one of the above users, verify it manually here.")
    
if __name__ == '__main__':
    check_users()
