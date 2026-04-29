import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum, Count, Avg
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.http import FileResponse
from functools import wraps
import io
import logging
import random
from django.core.mail import send_mail

# Import models from app
from app.models import Login, AdminNotification, Trip, TripImage, Booking, TripUpdate, TripChat, Review, Report, TravelerNotification, PasswordResetOTP, EmailVerificationOTP
from app.utils import send_verification_otp

def mark_expired_trips():
    """Mark trips as expired if their end_date has passed"""
    Trip.objects.filter(
        end_date__lt=date.today(),
        status__in=['APPROVED', 'ONGOING', 'PAUSED']
    ).update(status='EXPIRED')


def index(request):
    featured_trips = Trip.objects.filter(status='APPROVED', start_date__gte=date.today()).order_by('-created_at')[:3]

    total_trips = Trip.objects.filter(
        status__in=['APPROVED', 'ONGOING', 'COMPLETED']
    ).count()
    total_travelers = Login.objects.filter(usertype='traveler').count()
    total_companies = Login.objects.filter(
        usertype='company',
        verification_status='APPROVED'
    ).count()
    completed_bookings = Booking.objects.filter(status='CONFIRMED').count()

    context = {
        'featured_trips': featured_trips,
        'total_trips': total_trips,
        'total_travelers': total_travelers,
        'total_companies': total_companies,
        'completed_bookings': completed_bookings,
    }

    return render(request, 'index.html', context)

def register(request):
    from app.models import SystemSetting
    if not SystemSetting.get_settings().allow_registrations:
        messages.error(request, "Public registrations are temporarily disabled by the administrator. Please try again later.")
        return redirect('index')

    if request.method == 'POST':
        # ... logic for registration ...
        # Simplified for restoration, assuming standard user creation based on model
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        usertype = request.POST.get('usertype', 'traveler')
        
        if Login.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username already exists")
            return redirect('register')

        if Login.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already registered")
            return redirect('register')

        if ' ' in username:
            messages.error(request, "Username must not contain spaces")
            return redirect('register')
            
        # 1. Check Matching
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('register')
            
        # 2. Check Password Strength
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long")
            return redirect('register')
            
        if not any(char.isdigit() for char in password):
            messages.error(request, "Password must contain at least one number")
            return redirect('register')
            
        if not any(char.isupper() for char in password):
            messages.error(request, "Password must contain at least one uppercase letter")
            return redirect('register')

        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in password):
             messages.error(request, "Password must contain at least one special character")
             return redirect('register')
            
        from django.db import IntegrityError
        try:
            user = Login.objects.create_user(username=username, email=email, password=password, usertype=usertype)
            user.view_password = password
        except IntegrityError as e:
            if 'username' in str(e).lower():
                messages.error(request, "Username already exists")
            elif 'email' in str(e).lower():
                messages.error(request, "Email already registered")
            else:
                messages.error(request, "An account with these details already exists.")
            return redirect('register')
        
        if usertype == 'traveler':
            first_name = request.POST.get('firstName')
            last_name = request.POST.get('lastName')
            
            if ' ' in first_name or ' ' in last_name:
                 user.delete()
                 messages.error(request, "First and Last Name must not contain spaces")
                 return redirect('register')
                 
            user.first_name = first_name
            user.last_name = last_name
            user.gender = request.POST.get('gender')
            user.phone = request.POST.get('phone')
            birth_date_str = request.POST.get('birth_date')
            
            # DOB validation - must be 15 years or older
            if birth_date_str:
                try:
                    from datetime import datetime
                    birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                    age = (date.today() - birth_date).days // 365
                    if age < 15:
                        user.delete()
                        messages.error(request, "You must be at least 15 years old to register.")
                        return redirect('register')
                    user.birth_date = birth_date
                except ValueError:
                    user.delete()
                    messages.error(request, "Invalid date format for birth date.")
                    return redirect('register')
            else:
                user.delete()
                messages.error(request, "Birth date is required for travelers.")
                return redirect('register')
            
        if usertype == 'company':
            user.company_name = request.POST.get('company_name')
            
            # create notification
            AdminNotification.objects.create(
                type='NEW_COMPANY',
                title='New Company Registered',
                message=f'Company {user.company_name} has registered.',
                company=user
            )
        
        # Registration logic
        from app.models import SystemSetting
        settings = SystemSetting.get_settings()
        
        if not settings.require_otp_verification:
            user.is_active = True
            user.email_verified = True
            user.save()
            messages.success(request, "Registration successful. You can now login.")
            return redirect('login')

        # Security: Keep user inactive until email is verified
        user.is_active = False
        user.email_verified = False
        user.save()

        # Send OTP using helper
        success, _ = send_verification_otp(request, user)

        # Store pending verification user id in session
        request.session['verify_email_user_id'] = user.id
        
        if success:
            messages.success(request, f'Registration successful! A code was sent to {user.email}.')
        else:
            messages.info(request, 'Registration successful! Please click "Resend Code" on the next page to receive your verification email.')
            
        return redirect('verify_email_otp')

    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Check if email exists first
        try:
            user_obj = Login.objects.get(email=email)
            
            # Check password directly since authenticate() returns None for inactive users
            if user_obj.check_password(password):
                user = user_obj
                
                from app.models import SystemSetting
                require_otp = SystemSetting.get_settings().require_otp_verification

                # Block login if email not verified
                if require_otp and not user.email_verified and not user.is_superuser:
                    request.session['verify_email_user_id'] = user.id
                    
                    # Auto-send fresh OTP on login attempt
                    success, wait_time = send_verification_otp(request, user)
                    if not success and wait_time > 0:
                        messages.warning(request, f'Please verify your email. A code was recently sent. Wait {wait_time}s to resend.')
                    elif success:
                        messages.info(request, 'A fresh verification code has been sent to your email.')
                    else:
                        messages.warning(request, 'Please verify your email address to continue.')
                        
                    return redirect('verify_email_otp')

                # Re-authenticate strictly for login()
                user_auth = authenticate(request, username=user.username, password=password)
                if user_auth is not None:
                    login(request, user_auth)
                    if user_auth.usertype == 'traveler':
                        return redirect('index')
                    elif user_auth.usertype == 'company':
                        return redirect('company_dashboard')
                    elif user_auth.is_superuser:
                        return redirect('admin_dashboard')
                    else:
                        return redirect('index')
                else:
                    if not user.is_active:
                        messages.error(request, "Your account has been deactivated.")
                    else:
                        messages.error(request, "Authentication failed.")
                    return redirect('login')
            else:
                messages.error(request, "Invalid password")
                return redirect('login')

        except Login.DoesNotExist:
            messages.error(request, "Email not registered")
            return redirect('login')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('index')


# ==========================================
# Email Verification (OTP Flow)
# ==========================================

def verify_email_otp(request):
    user_id = request.session.get('verify_email_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please register again or login.')
        return redirect('register')

    try:
        user = Login.objects.get(id=user_id)
    except Login.DoesNotExist:
        messages.error(request, 'User not found. Please register again.')
        return redirect('register')

    if user.email_verified:
        # Already verified, just go to login
        if 'verify_email_user_id' in request.session:
            del request.session['verify_email_user_id']
        messages.success(request, 'Your email is already verified. Please login.')
        return redirect('login')

    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        otp_record = EmailVerificationOTP.objects.filter(user=user).order_by('-created_at').first()

        if otp_record and otp_record.is_valid() and otp_record.otp_code == otp_entered:
            otp_record.is_used = True
            otp_record.save()
            user.email_verified = True
            user.is_active = True  # Activate account
            user.save()
            if 'verify_email_user_id' in request.session:
                del request.session['verify_email_user_id']
            messages.success(request, 'Email verified successfully! Your account is now active.')
            return redirect('login')
        else:
            messages.error(request, 'Invalid or expired code. Please try again or resend.')

    return render(request, 'traveler/verify_email_otp.html', {'email': user.email})


def resend_verification_otp(request):
    user_id = request.session.get('verify_email_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')

    try:
        user = Login.objects.get(id=user_id)
    except Login.DoesNotExist:
        return redirect('register')

    if user.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('login')

    success, wait_time = send_verification_otp(request, user)
    
    if success:
        messages.success(request, f'A new code has been sent to {user.email}.')
    elif wait_time > 0:
        messages.warning(request, f'Please wait {wait_time} seconds before requesting another code.')
    else:
        messages.error(request, 'Failed to send email. Please try again later.')

    return redirect('verify_email_otp')


def forgot_password(request):
    User = get_user_model()
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            # Generate 6-digit OTP
            otp_code = str(random.randint(100000, 999999))
            
            # Save OTP to database
            PasswordResetOTP.objects.create(user=user, otp_code=otp_code)
            
            # Send Email
            subject = 'Your Password Reset OTP - Travel Buddy'
            message = f'Hi {user.username},\n\nYour One-Time Password (OTP) for resetting your password is: {otp_code}\n\nThis code will expire in 10 minutes.'
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') else 'noreply@travelbuddy.com',
                [user.email],
                fail_silently=False,
            )
            
            # Save email in session to verify OTP next
            request.session['reset_email'] = user.email
            messages.success(request, f'An OTP has been sent to {user.email}. Please enter it below.')
            return redirect('verify_otp')
            
        except User.DoesNotExist:
            # For security, we do not explicitly say the email doesn't exist.
            messages.error(request, 'If an account exists with this email, an OTP has been sent.')
            # In a real app we might redirect back or still go to verify_otp
            return redirect('forgot_password')
            
    return render(request, 'traveler/forgot_password.html')

def verify_otp(request):
    if 'reset_email' not in request.session:
        messages.error(request, 'Please enter your email to request an OTP first.')
        return redirect('forgot_password')
        
    User = get_user_model()
    email = request.session['reset_email']
    user = User.objects.get(email=email)
    
    if request.method == 'POST':
        otp_entered = request.POST.get('otp')
        
        # Get latest OTP for user
        otp_record = PasswordResetOTP.objects.filter(user=user).order_by('-created_at').first()
        
        if otp_record and otp_record.is_valid() and otp_record.otp_code == otp_entered:
            otp_record.is_used = True
            otp_record.save()
            # Allow them to access the final reset page
            request.session['otp_verified'] = True
            messages.success(request, 'OTP verified successfully. Please enter your new password.')
            return redirect('reset_password_otp')
        else:
            messages.error(request, 'Invalid or expired OTP. Please try again or request a new one.')
            
    return render(request, 'traveler/verify_otp.html', {'email': email})

def reset_password_otp(request):
    if not request.session.get('otp_verified'):
        messages.error(request, 'Please verify your OTP before resetting password.')
        return redirect('verify_otp')
        
    User = get_user_model()
    email = request.session.get('reset_email')
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, 'Session issue. Please restart the password reset process.')
        return redirect('forgot_password')

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Check if new password is empty
        if not new_password:
            messages.error(request, 'New password cannot be empty')
            return render(request, 'traveler/reset_password_otp.html')
            
        # Check if passwords match
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'traveler/reset_password_otp.html')
            
        # Check password length
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long')
            return render(request, 'traveler/reset_password_otp.html')
            
        # Check for uppercase
        if not any(char.isupper() for char in new_password):
            messages.error(request, 'Password must contain at least one uppercase letter')
            return render(request, 'traveler/reset_password_otp.html')
            
        # Check for lowercase
        if not any(char.islower() for char in new_password):
            messages.error(request, 'Password must contain at least one lowercase letter')
            return render(request, 'traveler/reset_password_otp.html')
            
        # Check for digit
        if not any(char.isdigit() for char in new_password):
            messages.error(request, 'Password must contain at least one number')
            return render(request, 'traveler/reset_password_otp.html')
            
        # Check for special character
        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in new_password):
            messages.error(request, 'Password must contain at least one special character')
            return render(request, 'traveler/reset_password_otp.html')
        
        # All validations passed
        user.set_password(new_password)
        
        # Compatibility with the view_password system used elsewhere in the codebase
        if hasattr(user, 'view_password'):
            user.view_password = new_password
            
        user.save()
        
        # Clean up session
        del request.session['reset_email']
        del request.session['otp_verified']
        
        messages.success(request, 'Your password has been reset successfully! You can now log in.')
        return redirect('login')
            
    return render(request, 'traveler/reset_password_otp.html')

# ==========================================
# Traveler Dashboard
# ==========================================

@login_required
def user_dashboard(request):
    if request.user.usertype != 'traveler':
        return redirect('index')
        
    from datetime import date
    from django.db.models import Sum
    from app.models import Booking, Review
    
    # Total Trips
    total_trips = Booking.objects.filter(traveler=request.user, status='CONFIRMED').count()
    
    # Upcoming Trips
    upcoming_trips = Booking.objects.filter(
        traveler=request.user, 
        status='CONFIRMED', 
        trip__start_date__gte=date.today()
    ).count()
    
    # Reviews Given
    reviews_given = Review.objects.filter(reviewer=request.user).count()
    
    # Buddies (Total people brought along across all confirmed bookings)
    buddies_agg = Booking.objects.filter(traveler=request.user, status='CONFIRMED').aggregate(Sum('num_people'))
    buddies_count = (buddies_agg['num_people__sum'] or 0)
    
    # Recent Activity Feed
    activities = []
    
    # Add Account Creation
    activities.append({
        'type': 'account_created',
        'title': 'Account Created',
        'description': 'Joined the Travel Buddy platform.',
        'date': request.user.date_joined,
        'icon': 'fa-user-plus',
        'color_cls': 'bg-gray-300'
    })
    
    # Add Recent Bookings
    bookings = Booking.objects.filter(traveler=request.user, status='CONFIRMED').order_by('-booking_date')[:5]
    for booking in bookings:
        activities.append({
            'type': 'booking',
            'title': f'Booked: {booking.trip.title}',
            'description': f'Confirmed booking for {booking.num_people} traveler(s) to {booking.trip.destination}.',
            'date': booking.booking_date,
            'icon': 'fa-suitcase-rolling',
            'color_cls': 'bg-green-400'
        })
        
    # Add Recent Reviews
    reviews = Review.objects.filter(reviewer=request.user).order_by('-created_at')[:5]
    for review in reviews:
        activities.append({
            'type': 'review',
            'title': f'Reviewed: {review.trip.title}',
            'description': f'Left a {review.rating_overall}-star review.',
            'date': review.created_at,
            'icon': 'fa-star',
            'color_cls': 'bg-yellow-400'
        })
        
    # Sort activities by date descending (newest first)
    activities.sort(key=lambda x: x['date'], reverse=True)
    
    # Limit to top 5 activities for the feed
    recent_activity = activities[:5]
    
    context = {
        'user': request.user,
        'total_trips': total_trips,
        'upcoming_trips': upcoming_trips,
        'reviews_given': reviews_given,
        'buddies_count': buddies_count,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'user/dashboard.html', context)

@login_required
def edit_user_profile(request):
    if request.user.usertype != 'traveler':
        return redirect('index')
    
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.phone = request.POST.get('phone')
        user.bio = request.POST.get('bio')
        user.interests = request.POST.get('interests')
        user.gender = request.POST.get('gender')
        user.birth_date = request.POST.get('birth_date')
        
        # Handle profile picture if you have one, currently not in model explicitly for upload here but relying on default user model maybe?
        # For now just text fields
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('user_dashboard')
        
    return render(request, 'user/edit_profile.html', {'user': request.user})

@login_required
def user_settings(request):
    if request.user.usertype != 'traveler':
        return redirect('index')
    
    return render(request, 'user/settings.html', {'user': request.user})

@login_required
def change_username(request):
    if request.user.usertype != 'traveler':
        return redirect('index')
    
    if request.method == 'POST':
        new_username = request.POST.get('new_username', '').strip()
        
        if not new_username:
            messages.error(request, 'Username cannot be empty')
            return redirect('user_settings')
        
        if ' ' in new_username:
            messages.error(request, 'Username cannot contain spaces')
            return redirect('user_settings')
        
        if Login.objects.filter(username=new_username).exclude(id=request.user.id).exists():
            messages.error(request, 'Username already taken')
            return redirect('user_settings')
        
        request.user.username = new_username
        request.user.save()
        messages.success(request, 'Username changed successfully!')
        return redirect('user_settings')
    
    return redirect('user_settings')

@login_required
def change_password(request):
    if request.user.usertype != 'traveler':
        return redirect('index')
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Verify current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect')
            return redirect('user_settings')
        
        # Check if new password is empty
        if not new_password:
            messages.error(request, 'New password cannot be empty')
            return redirect('user_settings')
        
        # Check if passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match')
            return redirect('user_settings')
        
        # Check password length
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long')
            return redirect('user_settings')
        
        # Check for uppercase
        if not any(char.isupper() for char in new_password):
            messages.error(request, 'Password must contain at least one uppercase letter')
            return redirect('user_settings')
        
        # Check for lowercase
        if not any(char.islower() for char in new_password):
            messages.error(request, 'Password must contain at least one lowercase letter')
            return redirect('user_settings')
        
        # Check for digit
        if not any(char.isdigit() for char in new_password):
            messages.error(request, 'Password must contain at least one number')
            return redirect('user_settings')
        
        # Check for special character
        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in new_password):
            messages.error(request, 'Password must contain at least one special character')
            return redirect('user_settings')
        
        # Check if new password is same as current
        if request.user.check_password(new_password):
            messages.error(request, 'New password must be different from current password')
            return redirect('user_settings')
        
        # Update password
        request.user.set_password(new_password)
        request.user.view_password = new_password
        request.user.save()
        messages.success(request, 'Password changed successfully!')
        return redirect('user_settings')
    
    return redirect('user_settings')

def browse_trips(request):
    """Public page to browse and search approved trips"""
    from django.core.paginator import Paginator
    
    # Mark expired trips before showing
    mark_expired_trips()

    # Get only approved trips, exclude expired ones, AND exclude trips that have already started
    trips = Trip.objects.filter(status='APPROVED', start_date__gte=date.today()).exclude(status='EXPIRED').order_by('-created_at')

    # Get filter parameters
    vibe_filter = request.GET.get('vibe', '')
    search_query = request.GET.get('q', '')
    destination_filter = request.GET.get('destination', '')
    status_filter = request.GET.get('status', '')  # New filter for trip status

    # Apply vibe filter
    if vibe_filter:
        if vibe_filter == 'FREE':
            trips = trips.filter(price=0)
        else:
            trips = trips.filter(vibe_tag=vibe_filter)

    # Apply search filter
    if search_query:
        trips = trips.filter(
            Q(title__icontains=search_query) |
            Q(destination__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Apply destination filter
    if destination_filter:
        trips = trips.filter(destination__icontains=destination_filter)

    # Apply status filter (for trip status like ongoing, completed, etc.)
    if status_filter and status_filter == 'completed':
        trips = trips.filter(status='COMPLETED')
    elif status_filter and status_filter == 'active':
        trips = trips.filter(status='APPROVED')

    # Pagination - show 9 trips per page (3 columns x 3 rows)
    paginator = Paginator(trips, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get all vibe choices for filter sidebar
    vibe_choices = Trip.VIBE_CHOICES
    
    current_vibe_display = ""
    if vibe_filter:
        if vibe_filter == 'FREE':
            current_vibe_display = "Free Trips"
        else:
            # Find display name from choices
            for key, label in vibe_choices:
                if key == vibe_filter:
                    current_vibe_display = label
                    break
    
    # Count completed trips for dashboard
    completed_trips_count = Trip.objects.filter(status='COMPLETED').count()

    context = {
        'trips': page_obj,
        'vibe_choices': vibe_choices,
        'current_vibe': vibe_filter,
        'current_vibe_display': current_vibe_display,
        'search_query': search_query,
        'destination_filter': destination_filter,
        'status_filter': status_filter,
        'completed_trips_count': completed_trips_count,
        'page_obj': page_obj,
    }
    return render(request, 'search_trips.html', context)

def trip_detail(request, trip_id):
    """Public view for trip details"""
    trip = get_object_or_404(Trip, id=trip_id)
    
    # Increment View Count
    trip.view_count += 1
    trip.save(update_fields=['view_count'])
    
    # Only allow viewing approved trips unless the user is the owner or admin
    if trip.status != 'APPROVED':
        # Allow checking if user is owner or admin
        is_owner = request.user.is_authenticated and trip.company == request.user
        is_admin = request.user.is_authenticated and (request.user.is_superuser or request.user.usertype == 'admin')
        is_booked = request.user.is_authenticated and Booking.objects.filter(trip=trip, traveler=request.user, status='CONFIRMED').exists()
        
        if not (is_owner or is_admin or is_booked):
            messages.error(request, "This trip is not currently available.")
            return redirect('browse_trips')

    is_booked = False
    if request.user.is_authenticated and request.user.usertype == 'traveler':
        is_booked = Booking.objects.filter(trip=trip, traveler=request.user, status='CONFIRMED').exists()

    # Crowd Peek Logic - aggregate gender counts using booking-level breakdown when available
    confirmed_bookings = trip.bookings.filter(status='CONFIRMED')
    total_confirmed = 0

    avg_age = None
    gender_distribution = {'MALE': 0, 'FEMALE': 0, 'OTHER': 0}

    if confirmed_bookings.exists():
        ages = []
        for b in confirmed_bookings:
            # determine count for this booking
            try:
                # prefer explicit gender fields if present
                males = int(getattr(b, 'num_males', 0) or 0)
                females = int(getattr(b, 'num_females', 0) or 0)
                others = int(getattr(b, 'num_others', 0) or 0)
                booking_total = males + females + others
                # fallback to num_people if breakdown not provided
                if booking_total == 0:
                    booking_total = int(getattr(b, 'num_people', 0) or 0)
                    # infer gender from booker's profile
                    gender_key = b.traveler.gender.upper() if b.traveler.gender else 'OTHER'
                    if gender_key in gender_distribution:
                        gender_distribution[gender_key] += booking_total
                    else:
                        gender_distribution['OTHER'] += booking_total
                else:
                    gender_distribution['MALE'] += males
                    gender_distribution['FEMALE'] += females
                    gender_distribution['OTHER'] += others

                # ages: approximate using booker's age for all members of the booking
                if b.traveler.birth_date:
                    age = (date.today() - b.traveler.birth_date).days // 365
                    ages.extend([age] * booking_total)

                total_confirmed += booking_total
            except Exception:
                # defensive fallback
                booking_total = int(getattr(b, 'num_people', 0) or 0)
                gender_key = b.traveler.gender.upper() if b.traveler.gender else 'OTHER'
                if gender_key in gender_distribution:
                    gender_distribution[gender_key] += booking_total
                else:
                    gender_distribution['OTHER'] += booking_total
                if b.traveler.birth_date:
                    age = (date.today() - b.traveler.birth_date).days // 365
                    ages.extend([age] * booking_total)
                total_confirmed += booking_total

        if ages:
            avg_age = sum(ages) // len(ages)

    # Gender Profile Requirement Check
    needs_gender_update = False
    is_gender_eligible = True
    
    if request.user.is_authenticated and request.user.usertype == 'traveler':
        if not request.user.gender:
            if trip.gender_restriction != 'ANY':
                needs_gender_update = True
        else:
            if trip.gender_restriction == 'FEMALE_ONLY' and request.user.gender != 'FEMALE':
                is_gender_eligible = False
            elif trip.gender_restriction == 'MALE_ONLY' and request.user.gender != 'MALE':
                is_gender_eligible = False

    context = {
        'trip': trip,
        'images': trip.images.all().order_by('-id'),
        'is_booked': is_booked,
        'needs_gender_update': needs_gender_update,
        'is_gender_eligible': is_gender_eligible,
        'social_activities': trip.social_activities,
        'crowd_peek': {
            'total_travelers': total_confirmed,
            'avg_age': avg_age,
            'gender_distribution': gender_distribution
        }
    }
    return render(request, 'trip_detail.html', context)

@login_required
def book_trip(request, trip_id):
    if request.user.usertype != 'traveler':
        messages.error(request, "Only travelers can book trips.")
        return redirect('trip_detail', trip_id=trip_id)

    trip = get_object_or_404(Trip, id=trip_id)

    # Check status - cannot book expired trips or started trips
    if trip.status != 'APPROVED' or trip.is_paused or trip.status == 'EXPIRED':
        messages.error(request, "This trip is currently not accepting bookings.")
        return redirect('browse_trips')
        
    if trip.start_date < date.today():
        messages.error(request, "This trip has already started and cannot be booked.")
        return redirect('browse_trips')

    # Check capacity - only count confirmed bookings
    confirmed_count = trip.bookings.filter(status='CONFIRMED').aggregate(Sum('num_people'))['num_people__sum'] or 0
    if confirmed_count >= trip.max_capacity:
        messages.error(request, "Sorry, this trip is fully booked!")
        return redirect('trip_detail', trip_id=trip_id)

    # Check logic: Age Restriction
    if request.user.birth_date:
        user_age = (date.today() - request.user.birth_date).days // 365
        if user_age < trip.age_min:
            messages.error(request, f"You must be at least {trip.age_min} years old to book this trip. Your age: {user_age} years.")
            return redirect('trip_detail', trip_id=trip_id)
        if user_age > trip.age_max:
            messages.error(request, f"This trip is for travelers up to {trip.age_max} years old. Your age: {user_age} years.")
            return redirect('trip_detail', trip_id=trip_id)
    else:
        messages.error(request, "Please update your profile with your birth date to book this trip.")
        return redirect('edit_user_profile')

    # Check logic: Gender Restriction
    if trip.gender_restriction != 'ANY':
        user_gender = request.user.gender
        if not user_gender:
             messages.error(request, "Please update your profile with your gender to book this restricted trip.")
             return redirect('edit_user_profile')

        if trip.gender_restriction == 'FEMALE_ONLY' and user_gender != 'FEMALE':
             messages.error(request, "This trip is restricted to Female travelers only.")
             return redirect('trip_detail', trip_id=trip_id)
        elif trip.gender_restriction == 'MALE_ONLY' and user_gender != 'MALE':
             messages.error(request, "This trip is restricted to Male travelers only.")
             return redirect('trip_detail', trip_id=trip_id)

    if request.method == 'POST':
        # Read counts
        try:
            num_people = int(request.POST.get('num_people', 1))
            num_males = int(request.POST.get('num_males', 0))
            num_females = int(request.POST.get('num_females', 0))
            num_others = int(request.POST.get('num_others', 0))
        except Exception:
            num_people = 1
            num_males = num_females = num_others = 0

        # Ensure the gender breakdown sums to num_people
        breakdown_total = num_males + num_females + num_others
        if breakdown_total != num_people:
            # If they didn't provide breakdown, fallback to num_people and infer from user gender
            if breakdown_total == 0:
                if request.user.gender == 'MALE': num_males = num_people
                elif request.user.gender == 'FEMALE': num_females = num_people
                else: num_others = num_people
            else:
                messages.error(request, "The gender counts must add up to the total number of travelers.")
                return redirect('trip_detail', trip_id=trip_id)


        # Capacity check - only count confirmed bookings
        confirmed_count = trip.bookings.filter(status='CONFIRMED').aggregate(Sum('num_people'))['num_people__sum'] or 0
        if confirmed_count + num_people > trip.max_capacity:
            messages.error(request, f"Sorry, only {trip.max_capacity - confirmed_count} seats left!")
            return redirect('trip_detail', trip_id=trip_id)

        total_price = trip.price * num_people

        # Check if there's an existing pending booking
        existing_pending = Booking.objects.filter(
            traveler=request.user,
            trip=trip,
            status='PENDING',
        ).order_by('-booking_date').first()

        if existing_pending:
            booking = existing_pending
            booking.num_people = num_people
            booking.num_males = num_males
            booking.num_females = num_females
            booking.num_others = num_others
            booking.total_price = total_price
            booking.save()
        else:
            # Create booking (PENDING first, then will be confirmed after payment)
            booking = Booking.objects.create(
                traveler=request.user,
                trip=trip,
                num_people=num_people,
                num_males=num_males,
                num_females=num_females,
                num_others=num_others,
                total_price=total_price,
                status='PENDING'
            )

        return redirect('booking_confirmation', booking_id=booking.id)

    return redirect('trip_detail', trip_id=trip_id)

@login_required
def booking_confirmation(request, booking_id):
    if request.user.is_superuser or request.user.usertype == 'admin':
        booking = get_object_or_404(Booking, id=booking_id)
    else:
        booking = get_object_or_404(Booking, id=booking_id, traveler=request.user)
    return render(request, 'booking_confirmation.html', {'booking': booking})

@login_required
def payment_mock(request, booking_id):
    import razorpay
    
    if request.user.is_superuser or request.user.usertype == 'admin':
        booking = get_object_or_404(Booking, id=booking_id)
    else:
        booking = get_object_or_404(Booking, id=booking_id, traveler=request.user)
    trip = booking.trip
    
    company_has_razorpay = bool(trip.company.razorpay_key_id and trip.company.razorpay_key_secret)
    razorpay_order_id = None
    
    # 1. Create Razorpay Order if keys exist AND it's a GET request
    if request.method == 'GET' and company_has_razorpay:
        try:
            client = razorpay.Client(auth=(trip.company.razorpay_key_id, trip.company.razorpay_key_secret))
            # Amount is in paise (Multiply by 100)
            data = {
                "amount": int(booking.total_price * 100),
                "currency": "INR",
                "receipt": f"receipt_{booking.id}",
                "payment_capture": 1
            }
            payment = client.order.create(data=data)
            razorpay_order_id = payment['id']
        except Exception as e:
            # Handle specific common errors for better UX
            error_msg = str(e).lower()
            if "authentication" in error_msg:
                friendly_error = "Payment gateway authentication failed. Using secure mock mode instead."
            elif "connection" in error_msg or "name" in error_msg:
                friendly_error = "Could not reach payment gateway. Using secure mock mode instead."
            else:
                friendly_error = f"Payment gateway error: {str(e)}. Using secure mock mode instead."
            
            messages.info(request, friendly_error)
            company_has_razorpay = False # Fallback to mock payment
            razorpay_order_id = None

    
    if request.method == 'POST':
        # Verify Razorpay signature if it was a real payment (Optional but secure)
        # We assume if POST happens, payment is either mock-completed or razorpay-completed
        
        # Final capacity check before confirming - only count confirmed bookings
        confirmed_count = trip.bookings.filter(status='CONFIRMED').aggregate(Sum('num_people'))['num_people__sum'] or 0
        if confirmed_count + booking.num_people > trip.max_capacity:
            messages.error(request, "Sorry, this trip just got fully booked. We cannot confirm your booking.")
            booking.status = 'CANCELLED'
            booking.save()
            return redirect('trip_detail', trip_id=trip.id)
            
        # Simulate payment success
        booking.status = 'CONFIRMED'
        booking.save()
        
        # Update trip capacity with only confirmed bookings count
        trip.current_bookings = trip.bookings.filter(status='CONFIRMED').aggregate(Sum('num_people'))['num_people__sum'] or 0
        trip.save()

        # Generate and Send HTML Receipt Email
        try:
            from django.template.loader import render_to_string
            from django.utils.html import strip_tags
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            import threading
            
            subject = f'Booking Confirmation for {trip.title} - Travel Buddy'
            html_content = render_to_string('booking_confirmation_email.html', {'booking': booking})
            text_content = strip_tags(html_content)
            
            def send_email_async():
                msg = EmailMultiAlternatives(
                    subject,
                    text_content,
                    settings.EMAIL_HOST_USER,
                    [request.user.email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=True)
                
            threading.Thread(target=send_email_async).start()
        except Exception as e:
            print(f"Failed to send confirmation email: {str(e)}")

        return redirect('booking_success', booking_id=booking.id)
        
    context = {
        'booking': booking,
        'has_razorpay': company_has_razorpay,
        'razorpay_order_id': razorpay_order_id,
        'razorpay_key_id': trip.company.razorpay_key_id if company_has_razorpay else None
    }
    return render(request, 'payment_mock.html', context)

@login_required
def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, traveler=request.user)
    return render(request, 'booking_success.html', {'booking': booking})

@login_required
def submit_review(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, traveler=request.user)
    
    # Check if already reviewed
    if hasattr(booking, 'review'):
        messages.error(request, "You have already reviewed this trip.")
        return redirect('my_bookings')
    
    # Check if trip has started
    if booking.trip.start_date > date.today():
        messages.error(request, "You can only review a trip after it has started.")
        return redirect('my_bookings')
        
    if request.method == 'POST':
        rating_overall = int(request.POST.get('rating_overall', 5))
        rating_social = int(request.POST.get('rating_social', 5))
        rating_logistics = int(request.POST.get('rating_logistics', 5))
        rating_safety = int(request.POST.get('rating_safety', 5))
        comment = request.POST.get('comment', '')
        
        Review.objects.create(
            trip=booking.trip,
            booking=booking,
            reviewer=request.user,
            rating_overall=rating_overall,
            rating_social_vibe=rating_social,
            rating_logistics=rating_logistics,
            rating_safety=rating_safety,
            comment=comment
        )

        return redirect('trip_detail', trip_id=booking.trip.id)
        
    return render(request, 'reviews/submit_review.html', {'booking': booking})

@login_required
def my_bookings(request):
    """Traveler's bookings page"""
    if request.user.usertype != 'traveler':
        return redirect('index')
    
    confirmed_trip_ids = Booking.objects.filter(
        traveler=request.user,
        status='CONFIRMED',
    ).values_list('trip_id', flat=True)

    bookings = (
        Booking.objects.filter(traveler=request.user)
        .exclude(status='PENDING', trip_id__in=confirmed_trip_ids)
        .order_by('-booking_date')
    )
    return render(request, 'traveler/my_bookings.html', {'bookings': bookings})

@login_required
def mark_traveler_notification_read(request, notification_id):
    notification = get_object_or_404(TravelerNotification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    # Redirect back to where the user came from
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
        
    return redirect('my_bookings')

def profile_redirect(request):
    """Redirect to the correct profile/dashboard based on user type"""
    if request.user.is_superuser or request.user.usertype == 'admin':
        return redirect('admin_dashboard')
    elif request.user.usertype == 'company':
        return redirect('company_profile')
    else:
        return redirect('user_dashboard')

@login_required
def download_receipt(request, booking_id):
    from django.contrib import messages
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Check permissions: must be the traveler, the company, or an admin
    is_traveler = request.user == booking.traveler
    is_company = False
    if hasattr(booking.trip, 'company') and booking.trip.company == request.user:
        is_company = True
    
    is_admin = request.user.is_superuser or request.user.usertype == 'admin'
    
    if not (is_traveler or is_company or is_admin):
        messages.error(request, "You don't have permission to view this receipt.")
        return redirect('index')
        
    if booking.status != 'CONFIRMED':
        messages.error(request, "Receipts are only available for confirmed bookings.")
        return redirect('my_bookings' if is_traveler else 'manage_bookings')
        
    return render(request, 'receipt.html', {'booking': booking})
