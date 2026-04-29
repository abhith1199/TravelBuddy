import random
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from app.models import EmailVerificationOTP

def send_verification_otp(request, user):
    """Helper to create and send verification OTP with 60s cooldown check"""
    # Check for cooldown
    last_otp = EmailVerificationOTP.objects.filter(user=user).order_by('-created_at').first()
    if last_otp:
        time_since = timezone.now() - last_otp.created_at
        if time_since < timedelta(seconds=60):
            return False, int(60 - time_since.total_seconds())

    # Invalidate old codes
    EmailVerificationOTP.objects.filter(user=user, is_used=False).update(is_used=True)

    # Create new OTP
    otp_code = str(random.randint(100000, 999999))
    EmailVerificationOTP.objects.create(user=user, otp_code=otp_code)

    subject = 'Verify Your Email - Travel Buddy'
    message = (
        f'Hi {user.username},\n\n'
        f'Welcome to Travel Buddy! Your verification code is:\n\n'
        f'  {otp_code}\n\n'
        f'Enter this 6-digit code on the verification page.\n'
        f'This code expires in 15 minutes.\n\n'
        f'- The Travel Buddy Team'
    )
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email], fail_silently=False)
        return True, 0
    except Exception:
        return False, -1
