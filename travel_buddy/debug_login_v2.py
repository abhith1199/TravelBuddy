import os
import django
import sys

# Redirect stdout to a file to avoid truncation issues in the tool output
sys.stdout = open('debug_output.txt', 'w')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_buddy.settings')
django.setup()

from app.models import Login

def check_users():
    print("Checking users in database...")
    users = Login.objects.all()
    if not users:
        print("No users found!")
        return

    for user in users:
        print(f"User: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  Is Active: {user.is_active}")
        print(f"  Usertype: {user.usertype}")
        print(f"  Password Hash Start: {user.password[:10] if user.password else 'None'}")
        if user.view_password:
             print(f"  Stored view_password: {user.view_password}")
        else:
             print("  No view_password stored (expected for old users)")
        print("-" * 20)

if __name__ == '__main__':
    try:
        check_users()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sys.stdout.close()
