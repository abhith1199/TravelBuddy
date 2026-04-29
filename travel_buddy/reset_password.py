import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_buddy.settings')
django.setup()

from app.models import Login

def reset_password(username, new_password):
    print(f"Resetting password for user: {username}")
    try:
        user = Login.objects.get(username=username)
        user.set_password(new_password)
        user.view_password = new_password
        user.save()
        print(f"Success! Password for '{username}' changed to '{new_password}'")
        print(f"view_password also updated.")
    except Login.DoesNotExist:
        print(f"Error: User '{username}' not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    reset_password('wandernest_admin', 'admin123')
