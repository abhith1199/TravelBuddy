import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from .models import Login, AdminNotification, Trip, TripImage, Booking, TripUpdate, TripChat, Review, Report, TravelerNotification
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.http import FileResponse
from .user_details_function import admin_get_user_details
from functools import wraps
import io

def mark_expired_trips():
    """Mark trips as expired if their end_date has passed"""
    Trip.objects.filter(
        end_date__lt=date.today(),
        status__in=['APPROVED', 'ONGOING', 'PAUSED']
    ).update(status='EXPIRED')

def index(request):
    featured_trips = Trip.objects.filter(status='APPROVED', start_date__gt=date.today()).order_by('-created_at')[:3]

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
    if request.method == 'POST':
        # ... logic for registration ...
        # Simplified for restoration, assuming standard user creation based on model
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        usertype = request.POST.get('usertype')
        
        if Login.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('register')

        if Login.objects.filter(email=email).exists():
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
            
        user = Login.objects.create_user(username=username, email=email, password=password, usertype=usertype)
        user.view_password = password
        
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
        
        user.save()
            
        messages.success(request, "Registration successful. Please login.")
        return redirect('login')
        
    return render(request, 'register.html')

def company_register_view(request):
    if request.method == 'POST':
        # Company Info
        company_name = request.POST.get('companyName')
        reg_number = request.POST.get('registrationNumber')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        
        # New Fields
        username = request.POST.get('username')
        contact_first_name = request.POST.get('contactFirstName')
        contact_last_name = request.POST.get('contactLastName')
        gender = request.POST.get('gender')
        website = request.POST.get('website')
        
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirmPassword')
        address = request.POST.get('address')
        description = request.POST.get('description')
        
        # 1. Validate phone number (10 digits or landline with area code)
        # Valid: 10 digit mobile (9876543210) or landline with area code (0124567890 or 2024567890)
        import re
        phone_pattern = re.compile(r'^\d{10}$')  # 10 digits (mobile or landline)
        
        if not phone or not phone_pattern.match(phone):
            messages.error(request, "Phone number must be 10 digits (mobile: 9XXXXXXXXX or landline: 0/2XXXXXXXXX)")
            return redirect('company_register')
        
        # 2. Check Matching
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('company_register')
            
        # 3. Check Password Strength
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long")
            return redirect('company_register')
            
        if not any(char.isdigit() for char in password):
            messages.error(request, "Password must contain at least one number")
            return redirect('company_register')
            
        if not any(char.isupper() for char in password):
            messages.error(request, "Password must contain at least one uppercase letter")
            return redirect('company_register')
            
        if not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for char in password):
             messages.error(request, "Password must contain at least one special character")
             return redirect('company_register')

        if Login.objects.filter(email=email).exists():
            messages.error(request, "Email already registered")
            return redirect('company_register')
            
        if Login.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('company_register')
            
        if ' ' in username:
             messages.error(request, "Username must not contain spaces")
             return redirect('company_register')

        if ' ' in contact_first_name or ' ' in contact_last_name:
             messages.error(request, "Contact Name must not contain spaces")
             return redirect('company_register')
             
        # Create user instance with all fields
        user = Login.objects.create_user(
            username=username, 
            email=email, 
            password=password,
            usertype='company',
            company_name=company_name,
            registration_number=reg_number,
            company_phone=phone,
            company_address=address,
            company_description=description,
            contact_first_name=contact_first_name,
            contact_last_name=contact_last_name,
            gender=gender,
            website=website,
            view_password=password
        )
        
        # Create notification for admin
        AdminNotification.objects.create(
            type='NEW_COMPANY',
            title='New Company Registered',
            message=f'Company {company_name} has registered and needs verification.',
            company=user
        )
        
        messages.success(request, "Company registration successful! Please login to complete verification.")
        return redirect('login')
        
    return render(request, 'company/register.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Check if email exists first
        try:
            user_obj = Login.objects.get(email=email)
            if not user_obj.is_active:
                messages.error(request, "Account deactivated")
                return redirect('login')
                
            # Authenticate using the username from the found user object
            user = authenticate(request, username=user_obj.username, password=password)
            
            if user is not None:
                login(request, user)
                if user.usertype == 'traveler':
                    return redirect('index')
                elif user.usertype == 'company':
                    return redirect('company_dashboard')
                elif user.is_superuser:
                    return redirect('admin_dashboard')
                else:
                    return redirect('index')
            else:
                messages.error(request, "Invalid password")
                return redirect('login')
                
        except Login.DoesNotExist:
            messages.error(request, "Email not registered")
            return redirect('login')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required
def user_dashboard(request):
    if request.user.usertype != 'traveler':
        return redirect('index')
    return render(request, 'user/dashboard.html', {'user': request.user})

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
        password = request.POST.get('password', '')
        
        # Validate new username
        if not new_username:
            messages.error(request, 'New username cannot be empty')
            return redirect('user_settings')
        
        # Check for spaces in username
        if ' ' in new_username:
            messages.error(request, 'Username must not contain spaces')
            return redirect('user_settings')
        
        # Check if username already exists
        if Login.objects.filter(username=new_username).exclude(id=request.user.id).exists():
            messages.error(request, 'Username already exists. Please choose a different one')
            return redirect('user_settings')
        
        # Verify password
        if not request.user.check_password(password):
            messages.error(request, 'Password is incorrect')
            return redirect('user_settings')
        
        # Update username
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

@login_required
def admin_dashboard(request):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
    
    # Get key metrics
    suspended_trips = Trip.objects.filter(status='SUSPENDED').count()
    active_trips = Trip.objects.filter(status='APPROVED').count()
    total_bookings = Booking.objects.filter(status='CONFIRMED').count()
    total_revenue = Booking.objects.filter(status='CONFIRMED').aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    context = {
        'notifications': notifications[:5],
        'verification_notifications': notifications,
        'suspended_trips': suspended_trips,
        'active_trips': active_trips,
        'total_bookings': total_bookings,
        'total_revenue': total_revenue,
    }
    return render(request, 'admin/dashboard.html', context)

@login_required
def admin_verification_list(request):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    # Base queryset
    companies_list = Login.objects.filter(usertype='company').order_by('-date_joined')
    
    # Calculate Stats
    total_companies = companies_list.count()
    pending_count = companies_list.filter(verification_status='PENDING_VERIFICATION').count()
    approved_count = companies_list.filter(verification_status='APPROVED').count()
    rejected_count = companies_list.filter(verification_status='REJECTED').count()
    
    # Filtering
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'PENDING_VERIFICATION':
        companies = companies_list.filter(verification_status='PENDING_VERIFICATION')
    elif status_filter == 'APPROVED':
        companies = companies_list.filter(verification_status='APPROVED')
    elif status_filter == 'REJECTED':
        companies = companies_list.filter(verification_status='REJECTED')
    else:
        companies = companies_list

    # Mark verification-related notifications as read
    AdminNotification.objects.filter(
        is_read=False, 
        type__in=['NEW_COMPANY', 'VERIFICATION_SUBMITTED']
    ).update(is_read=True)

    # Fetch remaining notifications
    notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
    
    return render(request, 'admin/verification_management.html', {
        'companies': companies,
        'verification_notifications': notifications,
        'total_companies': total_companies,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'status_filter': status_filter
    })

@login_required
def admin_user_management(request):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
        
    # Stats logic
    total_users = Login.objects.count()
    total_companies = Login.objects.filter(usertype='company').count()
    total_regular_users = Login.objects.filter(usertype='traveler').count()
    total_admins = Login.objects.filter(Q(is_superuser=True) | Q(usertype='admin')).count()
    
    # Filter logic
    users = Login.objects.all().order_by('-date_joined')
    user_type_filter = request.GET.get('user_type', '')
    
    if user_type_filter == 'company':
        users = users.filter(usertype='company')
    elif user_type_filter == 'regular':
        users = users.filter(usertype='traveler')
    elif user_type_filter == 'admin':
        users = users.filter(Q(is_superuser=True) | Q(usertype='admin'))
        
    context = {
        'users': users,
        'total_users': total_users, 
        'total_companies': total_companies,
        'total_regular_users': total_regular_users,
        'total_admins': total_admins,
        'user_type_filter': user_type_filter
    }
    return render(request, 'admin/user_management.html', context)

# ... helper for admin user actions ...
@login_required
def admin_toggle_user_status(request, user_id):
    if not request.user.is_superuser:
        return redirect('index')
    user = get_object_or_404(Login, id=user_id)
    user.is_active = not user.is_active
    user.save()
    messages.success(request, f"User {user.username} {'activated' if user.is_active else 'deactivated'}")
    return redirect('admin_user_management')

@login_required
def admin_delete_user(request, user_id):
    if not request.user.is_superuser:
        return redirect('index')
    user = get_object_or_404(Login, id=user_id)
    user.delete()
    messages.success(request, "User deleted")
    return redirect('admin_user_management')

@login_required
def company_dashboard(request):
    if request.user.usertype != 'company':
        return redirect('index')
    
    # Mark expired trips before showing dashboard
    mark_expired_trips()
        
    # Tier System Update Logic
    total_trips = Trip.objects.filter(company=request.user).count()
    total_bookings = Booking.objects.filter(trip__company=request.user, status='CONFIRMED').count()
    
    current_tier = request.user.tier
    new_tier = 'NEWBIE'
    
    # Tier Criteria: 
    # Elite: > 10 Trips AND > 50 Bookings
    # Pro: > 5 Trips
    if total_trips > 10 and total_bookings > 50:
        new_tier = 'ELITE'
    elif total_trips > 5:
        new_tier = 'PRO'
        
    if current_tier != new_tier:
        # Update user tier
        request.user.tier = new_tier
        request.user.save(update_fields=['tier'])
        
        # User Feedback
        if new_tier == 'ELITE':
             messages.success(request, "🎉 Congratulations! You've been upgraded to Elite Operator status!")
        elif new_tier == 'PRO' and current_tier == 'NEWBIE':
             messages.success(request, "🎉 Congratulations! You've been upgraded to Pro status!")
             
    # Fetch recent trips
    recent_trips = Trip.objects.filter(company=request.user).order_by('-created_at')[:5]
    
    # Calculate Stats
    active_trips_count = Trip.objects.filter(company=request.user, status__in=['APPROVED', 'ONGOING']).count()
    expired_trips_count = Trip.objects.filter(company=request.user, status='EXPIRED').count()
    total_revenue = Booking.objects.filter(trip__company=request.user, status='CONFIRMED').aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    # Calculate trust score from all trip reviews
    from django.db.models import Avg
    trips = Trip.objects.filter(company=request.user)
    trust_scores = [trip.get_trust_score() for trip in trips]
    trust_score = round(sum(trust_scores) / len(trust_scores), 2) if trust_scores and any(trust_scores) else 0
             
    context = {
        'total_trips': total_trips,
        'total_bookings': total_bookings,
        'recent_trips': recent_trips,
        'active_trips_count': active_trips_count,
        'expired_trips_count': expired_trips_count,
        'total_revenue': total_revenue,
        'trust_score': trust_score,
    }
    return render(request, 'company/dashboard.html', context)

@login_required
def verify_company(request):
    if request.user.usertype != 'company':
        return redirect('index')
    
    # If already verified or undergoing review, don't show the form again
    if request.user.verification_status == 'APPROVED':
        messages.info(request, "Your company is already verified.")
        return redirect('company_dashboard')
        
    if request.user.verification_status == 'PENDING_VERIFICATION' and request.user.license_document:
        messages.info(request, "Your verification is already under review. We will notify you once completed.")
        return redirect('company_dashboard')
    
    if request.method == 'POST':
        user = request.user
        
        # Text Fields
        user.tourism_license_number = request.POST.get('tourismLicenseNumber')
        user.gst_number = request.POST.get('gstNumber')
        user.business_type = request.POST.get('businessType')
        # Established year validation: must be an integer and strictly before current year
        est_year_raw = request.POST.get('establishedYear')
        if est_year_raw:
            try:
                est_year = int(est_year_raw)
                current_year = date.today().year
                if est_year >= current_year:
                    messages.error(request, "Established year must be before the current year.")
                    return redirect('company_verification')
                user.established_year = est_year
            except ValueError:
                messages.error(request, "Established year must be a valid year (numbers only).")
                return redirect('company_verification')
        user.company_description = request.POST.get('companyDescription')
        
        # Handle Services (Checkbox list)
        services = request.POST.getlist('services')
        if services:
            user.services_offered = ", ".join(services)
            
        # File Uploads
        if 'licenseDocument' in request.FILES:
            user.license_document = request.FILES['licenseDocument']
            user.license_document_status = 'PENDING_REVIEW'
            
        if 'governmentId' in request.FILES:
            user.government_id = request.FILES['governmentId']
            user.government_id_status = 'PENDING_REVIEW'
            
        # Update Verification Status
        user.verification_status = 'PENDING_VERIFICATION'
        user.save()
        
        # Notify Admin
        AdminNotification.objects.create(
            type='VERIFICATION_SUBMITTED',
            title='Verification Submitted',
            message=f'Company {user.company_name} has submitted verification documents.',
            company=user
        )
        
        messages.success(request, "Verification documents submitted successfully! Admin will review them shortly.")
        return redirect('company_dashboard')
        
    return render(request, 'company/verification.html')

@login_required
def company_profile(request):
    """View and manage company's own profile"""
    if request.user.usertype != 'company':
        return redirect('index')
    
    user = request.user
    context = {
        'company': user,
        'verification_status': user.verification_status,
        'needs_verification': user.verification_status == 'PENDING_VERIFICATION' and not (user.license_document and user.government_id),
        'is_rejected': user.verification_status == 'REJECTED',
    }
    return render(request, 'company/profile.html', context)

@login_required
def edit_company_profile(request):
    """Edit company profile details"""
    if request.user.usertype != 'company':
        return redirect('index')
    
    user = request.user
    
    if request.method == 'POST':
        # Validate contact phone (10 digits)
        import re
        contact_phone = request.POST.get('contact_phone', '').strip()
        
        if contact_phone:
            phone_pattern = re.compile(r'^\d{10}$')
            if not phone_pattern.match(contact_phone):
                messages.error(request, "Contact phone must be 10 digits (mobile: 9XXXXXXXXX or landline: 0/2XXXXXXXXX)")
                return redirect('edit_company_profile')
        
        # Update Company Info
        user.company_name = request.POST.get('company_name')
        user.registration_number = request.POST.get('registration_number')
        user.company_phone = request.POST.get('company_phone')
        user.website = request.POST.get('website')
        user.company_address = request.POST.get('company_address')
        # Validate established year: must be integer and before current year
        est_year_raw = request.POST.get('established_year', '').strip()
        if est_year_raw:
            try:
                est_year = int(est_year_raw)
                current_year = date.today().year
                if est_year >= current_year:
                    messages.error(request, "Established year must be before the current year.")
                    return redirect('edit_company_profile')
                user.established_year = est_year
            except ValueError:
                messages.error(request, "Established year must be a valid year (numbers only).")
                return redirect('edit_company_profile')
        else:
            user.established_year = None
        
        # New Fields
        user.company_description = request.POST.get('company_description')
        user.services_offered = request.POST.get('services_offered')
        user.business_type = request.POST.get('business_type')
        user.gst_number = request.POST.get('gst_number')
        user.tourism_license_number = request.POST.get('tourism_license_number')
        
        # Update Contact Info
        user.contact_first_name = request.POST.get('contact_first_name')
        user.contact_last_name = request.POST.get('contact_last_name')
        user.gender = request.POST.get('gender')
        user.contact_position = request.POST.get('contact_position')
        user.contact_phone = contact_phone
        
        # Update Email (Standard User Field)
        user.email = request.POST.get('email')
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('company_profile')
        
    return render(request, 'company/edit_profile.html', {'company': user})


@login_required
def reupload_documents(request):
    """Handle document re-upload for rejected verifications"""
    if request.user.usertype != 'company':
        return redirect('index')
    
    user = request.user
    
    if request.method == 'POST':
        license_doc = request.FILES.get('licenseDocument')
        gov_id = request.FILES.get('governmentId')
        
        has_updates = False
        
        if license_doc and user.license_document_status == 'REJECTED':
            user.license_document = license_doc
            user.license_document_status = 'PENDING_REVIEW'
            has_updates = True
            
        if gov_id and user.government_id_status == 'REJECTED':
            user.government_id = gov_id
            user.government_id_status = 'PENDING_REVIEW'
            has_updates = True
            
        if has_updates:
            # If everything that was rejected is now pending/approved, reset general status
            if (user.license_document_status in ['APPROVED', 'PENDING_REVIEW']) and \
               (user.government_id_status in ['APPROVED', 'PENDING_REVIEW']):
                user.verification_status = 'PENDING_VERIFICATION'
            
            user.save()
            
            # Notify admin about document resubmission
            doc_types = []
            if license_doc:
                doc_types.append('License')
            if gov_id:
                doc_types.append('Government ID')
            
            AdminNotification.objects.create(
                type='DOCUMENT_RESUBMITTED',
                title='Document Resubmitted',
                message=f'Company {user.company_name} has resubmitted {", ".join(doc_types)} for review.',
                company=user
            )
            
            messages.success(request, "Documents re-uploaded successfully. Your account is now back in review.")
            return redirect('company_dashboard')
        else:
            messages.warning(request, "No eligible documents were uploaded.")

    return render(request, 'company/reupload_documents.html', {'company': user})
    
@login_required
def create_trip(request):
    if request.user.usertype != 'company' or request.user.verification_status != 'APPROVED':
        messages.error(request, "Only verified companies can create trips.")
        return redirect('company_dashboard')

    if request.method == 'POST':
        try:
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            
            # Simple server-side validation
            from datetime import datetime, date
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if start_date <= date.today():
                messages.error(request, "Start date must be in the future.")
                return render(request, 'company/create_trip_simple.html')
                
            if end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
                return render(request, 'company/create_trip_simple.html')

            trip = Trip.objects.create(
                company=request.user,
                title=request.POST.get('title'),
                destination=request.POST.get('destination'),
                description=request.POST.get('description'),
                price=request.POST.get('price'),
                trip_type=request.POST.get('trip_type'),
                vibe_tag=request.POST.get('vibe_tag'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                duration_days=request.POST.get('duration_days'),
                max_capacity=request.POST.get('max_capacity'),
                age_min=request.POST.get('age_min'),
                age_max=request.POST.get('age_max'),
                gender_restriction=request.POST.get('gender_restriction'),
                itinerary_details=request.POST.get('itinerary_details'),
                social_activities=request.POST.get('social_activities'),
                status='PENDING_REVIEW'
            )
            
            # Handle Image Uploads
            images = request.FILES.getlist('trip_images')
            for index, img_file in enumerate(images):
                TripImage.objects.create(
                    trip=trip,
                    image=img_file,
                    is_cover=(index == 0)
                )
            messages.success(request, "Trip created successfully! It is now pending review.")
            return redirect('manage_trips')
        except Exception as e:
            messages.error(request, f"Error creating trip: {e}")

    return render(request, 'company/create_trip_simple.html')

@login_required
def manage_trips(request):
    if request.user.usertype != 'company':
        return redirect('index')
    
    # Mark expired trips before showing
    mark_expired_trips()
    
    trips = Trip.objects.filter(company=request.user)
    return render(request, 'company/manage_trips.html', {'trips': trips})

@login_required
def edit_trip(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, company=request.user)
    
    # Prevent editing expired trips
    if trip.status == 'EXPIRED':
        messages.error(request, "Cannot edit an expired trip.")
        return redirect('manage_trips')
    
    if request.method == 'POST':
        try:
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            
            # Simple server-side validation
            from datetime import datetime, date
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # For editing, we might allow today if it was already today, but user said "after current date"
            # To be safe and follow user instruction:
            if start_date <= date.today():
                messages.error(request, "Start date must be in the future.")
                return render(request, 'company/edit_trip.html', {'trip': trip})
                
            if end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
                return render(request, 'company/edit_trip.html', {'trip': trip})

            trip.title = request.POST.get('title')
            trip.destination = request.POST.get('destination')
            trip.description = request.POST.get('description')
            trip.price = request.POST.get('price')
            trip.trip_type = request.POST.get('trip_type')
            trip.vibe_tag = request.POST.get('vibe_tag')
            trip.start_date = request.POST.get('start_date')
            trip.end_date = request.POST.get('end_date')
            trip.duration_days = request.POST.get('duration_days')
            trip.max_capacity = request.POST.get('max_capacity')
            trip.age_min = request.POST.get('age_min')
            trip.age_max = request.POST.get('age_max')
            trip.gender_restriction = request.POST.get('gender_restriction')
            trip.itinerary_details = request.POST.get('itinerary_details')
            trip.social_activities = request.POST.get('social_activities')
            
            if trip.status in ['APPROVED', 'REJECTED']:
                trip.status = 'PENDING_REVIEW'
                messages.info(request, "Trip updated. Status reset to Pending Review.")
            
            # Handle New Image Uploads
            images = request.FILES.getlist('trip_images')
            existing_count = trip.images.count()
            for index, img_file in enumerate(images):
                TripImage.objects.create(
                    trip=trip,
                    image=img_file,
                    is_cover=(existing_count == 0 and index == 0) # Set cover if it's the first image ever
                )
            
            trip.save()
            
            # Notify Admin of update
            if trip.status == 'PENDING_REVIEW':
                AdminNotification.objects.create(
                    message=f"Trip Updated: '{trip.title}' by {request.user.company_name} needs review.",
                    type='ACTION_REQUIRED'
                )
                
            messages.success(request, "Trip updated successfully!")
            return redirect('manage_trips')
        except Exception as e:
            messages.error(request, f"Error updating trip: {e}")
            
    return render(request, 'company/edit_trip.html', {'trip': trip})

@login_required
def delete_trip_image(request, image_id):
    image = get_object_or_404(TripImage, id=image_id, trip__company=request.user)
    trip = image.trip
    was_cover = image.is_cover
    image.delete()
    
    # If the deleted image was a cover, make another one cover if exists
    if was_cover:
        next_image = trip.images.first()
        if next_image:
            next_image.is_cover = True
            next_image.save()
            
    messages.success(request, "Image removed successfully.")
    return redirect('edit_trip', trip_id=trip.id)

@login_required
def delete_trip(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, company=request.user)
    if request.method == 'POST':
        trip.delete()
        messages.success(request, "Trip deleted successfully.")
    return redirect('manage_trips')

@login_required
def view_bookings(request):
    if request.user.usertype != 'company':
        return redirect('index')
    
    # Get all bookings for trips owned by this company
    # Convert to list to ensure custom attributes are preserved in the template
    bookings = list(Booking.objects.filter(trip__company=request.user).select_related('traveler', 'trip').order_by('-booking_date'))
    
    # Pre-format traveler info to avoid template tag mangling by auto-formatter
    for booking in bookings:
        booking.traveler_initial = booking.traveler.username[0].upper() if booking.traveler.username else "?"
        booking.traveler_name = booking.traveler.username
        booking.traveler_email = booking.traveler.email
    
    context = {
        'bookings': bookings,
    }
    return render(request, 'company/bookings.html', context)

@login_required
def booking_detail(request, booking_id):
    if request.user.usertype != 'company':
        return redirect('index')
        
    # Get booking and ensure it belongs to this company's trip
    booking = get_object_or_404(Booking, id=booking_id, trip__company=request.user)
    
    context = {
        'booking': booking,
    }
    return render(request, 'company/booking_detail.html', context)

@login_required
def trip_insights(request, trip_id=0):
    if request.user.usertype != 'company':
        return redirect('index')
    
    trip = None
    if trip_id == 0:
        # Global Insights: Aggregate data from all trips
        trips = Trip.objects.filter(company=request.user)
        bookings = Booking.objects.filter(trip__in=trips, status='CONFIRMED').select_related('traveler')
        
        # Calculate global capacity
        total_current_bookings = bookings.aggregate(Sum('num_people'))['num_people__sum'] or 0
        total_max_capacity = sum(t.max_capacity for t in trips)
        remaining_seats = total_max_capacity - total_current_bookings
        capacity_pc = round((total_current_bookings / total_max_capacity * 100), 1) if total_max_capacity > 0 else 0
        
        context_data = {
            'trip': None,
            'title': "All Trips Overview",
            'destination': "Global Stats",
            'total_bookings': total_current_bookings,
            'max_capacity': total_max_capacity,
            'remaining_seats': remaining_seats,
            'capacity_pc': capacity_pc
        }
    else:
        # Specific Trip Insights
        trip = get_object_or_404(Trip, id=trip_id, company=request.user)
        bookings = Booking.objects.filter(trip=trip, status='CONFIRMED').select_related('traveler')
        
        # Calculate actual total people from bookings to ensure accuracy
        total_people = bookings.aggregate(Sum('num_people'))['num_people__sum'] or 0
        
        context_data = {
            'trip': trip,
            'title': trip.title,
            'destination': trip.destination,
            'total_bookings': total_people,
            'max_capacity': trip.max_capacity,
            'remaining_seats': trip.max_capacity - total_people,
            'capacity_pc': round((total_people / trip.max_capacity * 100), 1) if trip.max_capacity > 0 else 0
        }

    # Common Stats Calculation (Gender & Age) - Works on 'bookings' queryset
    # Common Stats Calculation (Gender & Age) - Works on 'bookings' queryset
    males = bookings.filter(traveler__gender__iexact='MALE').count()
    females = bookings.filter(traveler__gender__iexact='FEMALE').count()
    others = bookings.filter(traveler__gender__iexact='OTHER').count()
    
    total_gendered = males + females + others
    male_pc = (males / total_gendered * 100) if total_gendered > 0 else 0
    female_pc = (females / total_gendered * 100) if total_gendered > 0 else 0
    
    context = {
        'bookings_count': bookings.count(),
        'males': males,
        'females': females,
        'others': others,
        'male_pc': round(male_pc, 1),
        'female_pc': round(female_pc, 1),
        'bookings': bookings,
        **context_data
    }
    return render(request, 'company/trip_insights.html', context)

@login_required
def request_pause_trip(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, company=request.user)
    trip.is_pause_requested = True
    trip.save()
    
    # Notify Admin
    AdminNotification.objects.create(
        type='TRIP_PAUSE_REQUEST',
        title="Pause Request",
        message=f"Company {request.user.company_name} requested to pause bookings for {trip.title} due to crowd balance concerns.",
        company=request.user
    )
    
    messages.success(request, "Pause request sent to administrator.")
    return redirect('trip_insights', trip_id=trip.id)

@login_required
def request_unpause_trip(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, company=request.user)
    # For now, let's keep it simple: unpause resets the request but admin might need to approve
    # Actually, let's just make it auto-unpause or send another request
    trip.is_paused = False
    trip.is_pause_requested = False
    trip.status = 'APPROVED'
    trip.save()
    
    # Notify Admin that trip is active again
    AdminNotification.objects.create(
        type='GENERAL',
        title="Trip Unpaused",
        message=f"Company {request.user.company_name} has unpaused bookings for {trip.title}.",
        company=request.user
    )
    
    messages.success(request, "Trip bookings unpaused.")
    return redirect('trip_insights', trip_id=trip.id)


@login_required
def trip_communication(request, trip_id):
    """View for both company and travelers to see updates and chat"""
    trip = get_object_or_404(Trip, id=trip_id)

    # Check access: Company of the trip OR Traveler with CONFIRMED booking
    is_company = request.user == trip.company
    is_traveler = Booking.objects.filter(trip=trip, traveler=request.user, status='CONFIRMED').exists()

    if not (is_company or is_traveler or request.user.is_superuser):
        messages.error(request, "You do not have access to this trip's communication.")
        return redirect('index')

    # Check if trip is expired - prevent chat access
    if trip.status == 'EXPIRED':
        messages.error(request, "This trip has expired. Chat is no longer available.")
        return redirect('browse_trips')

    # Update last read timestamp
    from django.utils import timezone
    if is_company:
        trip.company_chat_last_read = timezone.now()
        trip.save(update_fields=['company_chat_last_read'])
    elif is_traveler:
        booking = Booking.objects.filter(trip=trip, traveler=request.user, status='CONFIRMED').first()
        if booking:
            booking.traveler_chat_last_read = timezone.now()
            booking.save(update_fields=['traveler_chat_last_read'])

    updates = trip.updates.all().order_by('-created_at')
    messages_chat = trip.chat_messages.all().order_by('created_at')

    for update in updates:
        update.formatted_date = update.created_at.strftime('%d %b, %H:%M')
        # Simple cleanup to prevent template tag mangling
        update.clean_content = update.content.strip()

    context = {
        'trip': trip,
        'updates': updates,
        'chat_messages': messages_chat,
        'is_company': is_company,
        'update_types': TripUpdate.UPDATE_TYPES,
        'chat_disabled': trip.status == 'EXPIRED',
    }

    if is_company:
        return render(request, 'company/communication.html', context)
    else:
        return render(request, 'traveler/trip_communication.html', context)


@login_required
def post_trip_update(request, trip_id):
    """Company posts a trip update"""
    trip = get_object_or_404(Trip, id=trip_id, company=request.user)

    if request.method == 'POST':
        update_type = request.POST.get('update_type')
        content = request.POST.get('content')

        if content:
            TripUpdate.objects.create(
                trip=trip,
                author=request.user,
                update_type=update_type,
                content=content
            )
            messages.success(request, f"Update posted: {dict(TripUpdate.UPDATE_TYPES).get(update_type)}")
        else:
            messages.error(request, "Update content cannot be empty.")

    return redirect('trip_communication', trip_id=trip.id)


@login_required
def send_trip_message(request, trip_id):
    """Send a message in the group chat"""
    trip = get_object_or_404(Trip, id=trip_id)

    # Check access
    is_company = request.user == trip.company
    is_traveler = Booking.objects.filter(trip=trip, traveler=request.user, status='CONFIRMED').exists()

    if not (is_company or is_traveler or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)

    # Prevent chatting if trip is completed or expired
    if trip.status in ['COMPLETED', 'EXPIRED', 'CANCELLED']:
        return JsonResponse({'status': 'error', 'message': f'Cannot chat on a {trip.status.lower()} trip'}, status=403)

    if request.method == 'POST':
        message_text = request.POST.get('message')
        if message_text:
            msg = TripChat.objects.create(
                trip=trip,
                sender=request.user,
                message=message_text
            )
            return JsonResponse({
                'status': 'success',
                'sender': msg.sender.username,
                'message': msg.message,
                'time': msg.created_at.strftime('%H:%M'),
            })

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@login_required
def company_chat(request):
    """Index page for all trip chats the company manages"""
    if request.user.usertype != 'company':
        return redirect('index')
    
    # Get trips that are at least approved or paused (active in some way)
    trips = Trip.objects.filter(company=request.user).exclude(status='DRAFT').order_by('-created_at')
    
    # Pre-format attributes to avoid template formatter splitting tags
    for trip in trips:
        trip.formatted_start_date = trip.start_date.strftime('%d %b %Y')
        trip.status_text = trip.get_status_display()
        
        # Pre-compute badge classes
        if trip.status == 'APPROVED':
            trip.status_class = 'success'
        elif trip.status == 'PAUSED':
            trip.status_class = 'warning'
        else:
            trip.status_class = 'secondary'
    
    return render(request, 'company/chat_index.html', {'trips': trips})

# Admin logic for document review - essential for notification context
@login_required
def admin_review_document(request, company_id, document_type=None):
    return redirect('admin_verification_management')

# Placeholder stubs to maintain URL compatibility
def admin_verify_company(request):
    return redirect('admin_verification_management')

@login_required
def admin_trip_management(request):
    """Admin view to manage and audit trips"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    # Mark expired trips before showing
    mark_expired_trips()
    
    # Get filter from query params
    status_filter = request.GET.get('status', 'PENDING_REVIEW')
    
    if status_filter == 'ALL':
        trips = Trip.objects.all().order_by('-created_at')
    elif status_filter == 'PAUSE_REQUESTED':
        trips = Trip.objects.filter(is_pause_requested=True).order_by('-created_at')
    elif status_filter == 'COMPLETED_AND_EXPIRED':
        # For admin dashboard, count COMPLETED and EXPIRED together
        trips = Trip.objects.filter(status__in=['COMPLETED', 'EXPIRED']).order_by('-created_at')
    else:
        trips = Trip.objects.filter(status=status_filter).order_by('-created_at')
    
    context = {
        'trips': trips,
        'current_filter': status_filter,
        'pending_count': Trip.objects.filter(status='PENDING_REVIEW').count(),
        'approved_count': Trip.objects.filter(status='APPROVED').count(),
        'rejected_count': Trip.objects.filter(status='REJECTED').count(),
        'suspended_count': Trip.objects.filter(status='SUSPENDED').count(),
        'pause_request_count': Trip.objects.filter(is_pause_requested=True).count(),
        'completed_expired_count': Trip.objects.filter(status__in=['COMPLETED', 'EXPIRED']).count(),
    }
    return render(request, 'admin/admin_trip_management.html', context)

@login_required
def approve_trip(request, trip_id):
    """Approve a trip"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    trip.status = 'APPROVED'
    trip.rejection_reason = ''  # Clear any previous rejection reason
    trip.save()
    
    # Create notification for company
    AdminNotification.objects.create(
        type='TRIP_APPROVED',
        title='Trip Approved',
        message=f'Your trip "{trip.title}" has been approved and is now live!',
        company=trip.company
    )
    
    messages.success(request, f'Trip "{trip.title}" has been approved.')
    return redirect('admin_trip_management')

@login_required
def reject_trip(request, trip_id):
    """Reject a trip with reason"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '').strip()
        
        if not rejection_reason:
            messages.error(request, 'Please provide a rejection reason.')
            return redirect('admin_trip_management')
        
        trip.status = 'REJECTED'
        trip.rejection_reason = rejection_reason
        trip.save()
        
        # Create notification for company
        AdminNotification.objects.create(
            type='TRIP_REJECTED',
            title='Trip Rejected',
            message=f'Your trip "{trip.title}" was rejected. Reason: {rejection_reason}',
            company=trip.company
        )
        
        messages.success(request, f'Trip "{trip.title}" has been rejected.')
        return redirect('admin_trip_management')
    
    return redirect('admin_trip_management')

@login_required
def admin_approve_pause(request, trip_id):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    trip.is_paused = True
    trip.is_pause_requested = False
    trip.status = 'PAUSED'
    trip.save()
    
    AdminNotification.objects.create(
        type='ACTION_REQUIRED',
        title="Pause Approved",
        message=f"Administrator has approved your pause request for {trip.title}. New bookings are now disabled.",
        company=trip.company
    )
    
    messages.success(request, f"Pause request approved for {trip.title}.")
    return redirect('admin_trip_management')

@login_required
def admin_reject_pause(request, trip_id):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    trip.is_pause_requested = False
    trip.save()
    
    AdminNotification.objects.create(
        type='ACTION_REQUIRED',
        title="Pause Request Rejected",
        message=f"Administrator has rejected your pause request for {trip.title}. Trip remains active.",
        company=trip.company
    )
    
    messages.success(request, f"Pause request rejected for {trip.title}.")
    return redirect('admin_trip_management')
    
    return render(request, 'admin/reject_trip.html', {'trip': trip})
@login_required
def trip_audit(request, trip_id):
    """Detailed view of a trip for admin auditing"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    capacity_percentage = trip.booking_percentage
    total_revenue = (
        Booking.objects.filter(trip=trip, status='CONFIRMED')
        .aggregate(total=Sum('total_price'))
        .get('total')
        or 0
    )
    
    # Debug: Print trip data to console
    print(f"Trip ID: {trip.id}")
    print(f"Destination: {trip.destination}")
    print(f"Start Date: {trip.start_date}")
    print(f"End Date: {trip.end_date}")
    print(f"Company Contact Last Name: {trip.company.contact_last_name if trip.company.contact_last_name else 'None'}")
    
    return render(
        request,
        'admin/trip_audit.html',
        {'trip': trip, 'capacity_percentage': capacity_percentage, 'total_revenue': total_revenue},
    )
@login_required
def suspend_trip(request, trip_id):
    """Suspend an approved trip temporarily"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    
    # Cannot suspend an expired trip
    if trip.status == 'EXPIRED':
        messages.error(request, "Cannot suspend an expired trip.")
        return redirect('trip_audit', trip_id=trip_id)
    
    trip.status = 'SUSPENDED'
    trip.save()
    
    # Create notification for company
    AdminNotification.objects.create(
        type='TRIP_SUSPENDED',
        title='Trip Suspended',
        message=f'Your trip "{trip.title}" has been temporarily suspended by admin.',
        company=trip.company
    )
    
    messages.success(request, f'Trip "{trip.title}" has been suspended.')
    return redirect('trip_audit', trip_id=trip_id)

@login_required
def unsuspend_trip(request, trip_id):
    """Restore a suspended trip to approved status"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    trip.status = 'APPROVED'
    trip.save()
    
    # Create notification for company
    AdminNotification.objects.create(
        type='TRIP_UNSUSPENDED',
        title='Trip Unsuspended',
        message=f'Your trip "{trip.title}" is now live again!',
        company=trip.company
    )
    
    messages.success(request, f'Trip "{trip.title}" has been unsuspended and is now live.')
    return redirect('trip_audit', trip_id=trip_id)

@login_required
def reverse_approval(request, trip_id):
    """Send approved trip back to pending review"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    trip.status = 'PENDING_REVIEW'
    trip.save()
    
    # Create notification for company
    AdminNotification.objects.create(
        type='TRIP_REVIEW_REVERSED',
        title='Trip Approval Reversed',
        message=f'Your trip "{trip.title}" approval has been reversed for re-review.',
        company=trip.company
    )
    
    messages.success(request, f'Trip "{trip.title}" sent back to pending review.')
    return redirect('trip_audit', trip_id=trip_id)

@login_required
def rereview_trip(request, trip_id):
    """Send rejected trip back to pending review for reconsideration"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    trip.status = 'PENDING_REVIEW'
    trip.rejection_reason = ''  # Clear rejection reason
    trip.save()
    
    # Create notification for company
    AdminNotification.objects.create(
        type='TRIP_REREVIEW',
        title='Trip Available for Re-review',
        message=f'Your trip "{trip.title}" is now available for re-review.',
        company=trip.company
    )
    
    messages.success(request, f'Trip "{trip.title}" is now available for re-review.')
    return redirect('trip_audit', trip_id=trip_id)

@login_required
def admin_delete_trip(request, trip_id):
    """Permanently delete a trip"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        return redirect('index')
    
    trip = get_object_or_404(Trip, id=trip_id)
    trip_title = trip.title
    company = trip.company
    trip.delete()
    
    # Create notification for company
    AdminNotification.objects.create(
        type='TRIP_DELETED',
        title='Trip Deleted',
        message=f'Your trip "{trip_title}" has been permanently deleted by admin.',
        company=company
    )
    
    messages.success(request, f'Trip "{trip_title}" has been permanently deleted.')
    return redirect('admin_trip_management')


def browse_trips(request):
    """Public page to browse and search approved trips"""
    from django.core.paginator import Paginator
    
    # Mark expired trips before showing
    mark_expired_trips()

    # Get only approved trips and exclude expired ones
    trips = Trip.objects.filter(status='APPROVED').exclude(status='EXPIRED').order_by('-created_at')

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

    # Pagination - show 6 trips per page
    paginator = Paginator(trips, 6)
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

    # Check status - cannot book expired trips
    if trip.status != 'APPROVED' or trip.is_paused or trip.status == 'EXPIRED':
        messages.error(request, "This trip is currently not accepting bookings.")
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
    if request.user.is_superuser or request.user.usertype == 'admin':
        booking = get_object_or_404(Booking, id=booking_id)
    else:
        booking = get_object_or_404(Booking, id=booking_id, traveler=request.user)
    trip = booking.trip
    
    if request.method == 'POST':
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
        
    return render(request, 'payment_mock.html', {'booking': booking})

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
def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, traveler=request.user)
    return render(request, 'booking_success.html', {'booking': booking})

@login_required
def submit_report(request, content_type_str, object_id):
    if request.method != 'POST':
        messages.error(request, "Invalid request method")
        return redirect('index')

    model_mapping = {
        'user': Login,
        'trip': Trip,
        'company': Login
    }
    
    model_class = model_mapping.get(content_type_str)
    if not model_class:
        messages.error(request, "Invalid report object")
        return redirect('index')
        
    obj = get_object_or_404(model_class, id=object_id)
    content_type = ContentType.objects.get_for_model(obj)
    
    reason = request.POST.get('reason')
    details = request.POST.get('details')
    
    Report.objects.create(
        reporter=request.user,
        content_type=content_type,
        object_id=object_id,
        reason=reason,
        details=details
    )
    
    messages.success(request, "Report submitted. Our safety team will review it shortly.")
    return redirect(request.META.get('HTTP_REFERER', 'index'))

@login_required
def admin_safety_dashboard(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
        
    # Mark all unread reports as read when the dashboard is viewed
    Report.objects.filter(is_read=False).update(is_read=True)
    
    reports = Report.objects.all().order_by('-created_at')
    
    notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
    
    return render(request, 'admin/safety_dashboard.html', {
        'reports': reports,
        'verification_notifications': notifications
    })

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


# --- ALIASES AND STUBS FOR URLS.PY COMPATIBILITY ---
register_view = register
# company_register_view is now properly defined as a separate function (see line 59)
company_verification = verify_company
user_dashboard = index # Placeholder
# mark_notification_read and mark_company_notification_read are now properly defined and implemented
admin_verification_management = admin_verification_list
@login_required
def approve_company_verification(request, company_id):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        messages.error(request, "Access denied")
        return redirect('index')
        
    if request.method == 'POST':
        company = get_object_or_404(Login, id=company_id)
        company.verification_status = 'APPROVED'
        company.verified_at = timezone.now()
        company.save()
        
        # Notify about approval
        AdminNotification.objects.create(
            type='VERIFICATION_APPROVED',
            title='Company Verified',
            message=f'Company {company.company_name} has been approved.',
            company=company
        )
        
        messages.success(request, f"Company {company.company_name} has been successfully approved.")
        
    return redirect('admin_verification_management')

@login_required
def reject_company_verification(request, company_id):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        messages.error(request, "Access denied")
        return redirect('index')
        
    if request.method == 'POST':
        company = get_object_or_404(Login, id=company_id)
        company.verification_status = 'REJECTED'
        company.rejection_reason = request.POST.get('rejection_reason', 'No reason provided')
        company.save()
        
        messages.warning(request, f"Company {company.company_name} has been rejected.")
        
    return redirect('admin_verification_management')

@login_required
def delete_company(request, company_id):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        messages.error(request, "Access denied")
        return redirect('index')
        
    if request.method == 'POST':
        company = get_object_or_404(Login, id=company_id)
        name = company.company_name
        company.delete()
        messages.success(request, f"Company {name} has been deleted.")
        
    return redirect('admin_verification_management')
admin_deactivate_user = admin_toggle_user_status
admin_activate_user = admin_toggle_user_status
# mark_company_notification_read is now properly defined and implemented
# Note: document_review and related views are merged into main definitions or added below.

@login_required
def document_review(request, company_id):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
    
    company = get_object_or_404(Login, id=company_id)
    return render(request, 'admin/document_review.html', {'company': company})

@login_required
def approve_document(request, company_id, document_type):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
        
    company = get_object_or_404(Login, id=company_id)
    # Only allow approving documents that are currently pending review.
    # If a document was rejected, admin must wait for the company to reupload (status will change to PENDING_REVIEW).
    if document_type == 'license':
        current_status = company.license_document_status
    else:
        current_status = company.government_id_status

    if current_status == 'REJECTED':
        messages.warning(request, "Cannot approve: document was rejected. Please ask the company to re-upload the document first.")
        return redirect('document_review', company_id=company.id)

    if current_status != 'PENDING_REVIEW':
        messages.warning(request, "No document pending review to approve.")
        return redirect('document_review', company_id=company.id)

    # Mark the specific document approved
    if document_type == 'license':
        company.license_document_status = 'APPROVED'
    elif document_type == 'government_id':
        company.government_id_status = 'APPROVED'

    company.save()

    # If both documents are approved, mark the company as verified
    if company.license_document_status == 'APPROVED' and company.government_id_status == 'APPROVED':
        company.verification_status = 'APPROVED'
        company.verified_at = timezone.now()
        company.save()
        messages.success(request, f"{document_type.replace('_', ' ').title()} approved. All documents approved! Company is now VERIFIED.")
    else:
        messages.success(request, f"{document_type.replace('_', ' ').title()} approved.")

    return redirect('document_review', company_id=company.id)

@login_required
def reject_document(request, company_id, document_type):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
        
    company = get_object_or_404(Login, id=company_id)

    # Capture rejection reason if provided
    reason = request.POST.get('rejection_reason', '').strip() if request.method == 'POST' else ''
    
    if document_type == 'license':
        company.license_document_status = 'REJECTED'
        if reason:
            company.license_rejection_reason = reason
    elif document_type == 'government_id':
        company.government_id_status = 'REJECTED'
        if reason:
            company.government_id_rejection_reason = reason
    
    # Reset verification status if documents are rejected
    company.verification_status = 'REJECTED'
    company.save()
    
    # Send notification to company about rejection
    # TravelerNotification model uses field name `type` (not `notification_type`) and
    # has a limited set of notification choices. Reuse `REVIEW_REMINDER` to
    # inform the company about the rejected document.
    TravelerNotification.objects.create(
        user=company,
        type='REVIEW_REMINDER',
        title=f'{document_type.replace("_", " ").title()} Rejected',
        message=f'Your {document_type.replace("_", " ")} document has been rejected. Reason: {reason if reason else "No reason provided"}. Please resubmit the document.',
    )
    
    messages.warning(request, f"{document_type.replace('_', ' ').title()} rejected. Notification sent to company.")
    return redirect('document_review', company_id=company.id)

@login_required
def admin_payment_management(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')

    bookings = Booking.objects.filter(status='CONFIRMED').order_by('-updated_at')
    
    # Calculate stats
    total_revenue = bookings.aggregate(Sum('total_price'))['total_price__sum'] or 0
    total_transactions = bookings.count()
    avg_transaction = total_revenue / total_transactions if total_transactions > 0 else 0
    
    # Per-Trip Stats
    trip_stats = Booking.objects.filter(status='CONFIRMED').values(
        'trip__title', 'trip__company__company_name'
    ).annotate(
        trip_revenue=Sum('total_price'),
        booking_count=Count('id')
    ).order_by('-trip_revenue')
    
    notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
    
    context = {
        'bookings': bookings,
        'total_revenue': total_revenue,
        'total_transactions': total_transactions,
        'avg_transaction': avg_transaction,
        'trip_stats': trip_stats,
        'verification_notifications': notifications
    }
    return render(request, 'admin/payment_management.html', context)

@login_required
def admin_review_management(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
    
    reviews = Review.objects.all().order_by('-created_at')
    
    notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
    
    return render(request, 'admin/review_management.html', {
        'reviews': reviews,
        'verification_notifications': notifications
    })


@login_required
def export_users_csv(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="travel_buddy_users.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Username', 'Email', 'User Type', 'Active', 'Date Joined', 'Last Login', 'Company Name'])

    users = Login.objects.all().order_by('-date_joined')
    for u in users:
        company_name = u.company_name if hasattr(u, 'company_name') else ('' if u.usertype != 'company' else u.username)
        writer.writerow([
            u.id,
            u.username,
            u.email,
            u.usertype,
            'Yes' if u.is_active else 'No',
            u.date_joined.strftime('%Y-%m-%d %H:%M') if u.date_joined else '',
            u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else '',
            company_name or ''
        ])

    return response

@login_required
def delete_review(request, review_id):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
        
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    messages.success(request, "Review deleted successfully.")
    return redirect('admin_review_management')

@login_required
def admin_reports_analytics(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
        
    # Gather stats
    # Notifications for base.html
    notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
    
    total_users = Login.objects.count()
    new_users_this_month = Login.objects.filter(date_joined__month=date.today().month).count()
    
    active_trips = Trip.objects.filter(status='APPROVED').count()
    
    total_bookings = Booking.objects.count()
    bookings_this_month = Booking.objects.filter(booking_date__month=date.today().month).count()
    
    total_revenue = Booking.objects.filter(status='CONFIRMED').aggregate(Sum('total_price'))['total_price__sum'] or 0
    
    # Top Performing Trips
    top_trips = Booking.objects.filter(status='CONFIRMED').values(
        'trip__title', 'trip__company__company_name'
    ).annotate(
        trip_revenue=Sum('total_price'),
        booking_count=Count('id')
    ).order_by('-trip_revenue')[:5]
    
    
    # Chart Data (Last 6 Months Revenue)
    today = date.today()
    chart_labels = []
    chart_data = []
    
    for i in range(5, -1, -1):
        # Calculate month start and end
        month_date = today.replace(day=1) 
        # Adjust for previous months
        # Note: simple month subtraction logic
        target_month = today.month - i
        target_year = today.year
        
        if target_month <= 0:
            target_month += 12
            target_year -= 1
            
        month_name = date(target_year, target_month, 1).strftime('%B')
        chart_labels.append(month_name)
        
        revenue = Booking.objects.filter(
            status='CONFIRMED', 
            booking_date__year=target_year,
            booking_date__month=target_month
        ).aggregate(Sum('total_price'))['total_price__sum'] or 0
        
        chart_data.append(float(revenue))

    context = {
        'verification_notifications': notifications,
        'total_users': total_users,
        'new_users_this_month': new_users_this_month,
        'active_trips': active_trips,
        'total_bookings': total_bookings,
        'bookings_this_month': bookings_this_month,
        'total_revenue': total_revenue,
        'top_trips': top_trips,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }
    return render(request, 'admin/reports_analytics.html', context)

@login_required
def mark_notification_read(request, notification_id):
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        messages.error(request, "Access denied")
        return redirect('index')
    
    # Admin can mark any notification as read
    notification = get_object_or_404(AdminNotification, id=notification_id)
    
    # If user wants to "delete" (hide from list), we can just mark read (since list shows only unread)
    # OR genuinely delete it. Given query "mark as unread delete", functionality implies removal.
    # Current implementation simply marks it as read, which removes it from the "unread" filter views.
    notification.is_read = True
    notification.save()
    
    # If explicit delete is requested (optional enhancement)
    if request.GET.get('action') == 'delete':
        notification.delete()
    
    # Redirect back to previous page or where specified
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('admin_dashboard')

@login_required
def mark_all_notifications_read(request):
    """Mark all unread admin notifications as read"""
    if not (request.user.is_superuser or request.user.usertype == 'admin'):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
        messages.error(request, "Access denied")
        return redirect('index')
        
    AdminNotification.objects.filter(is_read=False).update(is_read=True)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'All notifications marked as read'})
    
    messages.success(request, "All notifications marked as read.")
    
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('admin_dashboard')

@login_required
def mark_company_notification_read(request, notification_id):
    if request.user.usertype != 'company':
        messages.error(request, "Access denied")
        return redirect('index')
        
    notification = get_object_or_404(AdminNotification, id=notification_id, company=request.user)
    notification.is_read = True
    notification.save()
    
    # Redirect back to previous page or where specified
    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('company_dashboard')

@login_required
def admin_mark_notifications_read(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
        messages.error(request, "Access denied")
        return redirect('index')
        
    # Mark all unread notifications as read
    AdminNotification.objects.filter(is_read=False).update(is_read=True)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
         return JsonResponse({'status': 'success'})
         
    return redirect(request.META.get('HTTP_REFERER', 'admin_dashboard'))

@login_required
def admin_settings(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')
    
    from app.models import SystemSetting
    settings = SystemSetting.get_settings()
    
    if request.method == 'POST':
        # General Settings
        settings.maintenance_mode = 'maintenance_mode' in request.POST
        settings.allow_registrations = 'allow_registrations' in request.POST
        settings.platform_name = request.POST.get('platform_name', settings.platform_name)
        settings.support_email = request.POST.get('support_email', settings.support_email)
        
        # Financial Settings
        try:
            settings.commission_rate = float(request.POST.get('commission_rate', 5))
            settings.tax_rate = float(request.POST.get('tax_rate', 18))
        except ValueError:
            pass
            
        # Notification Settings
        settings.notify_new_partner = 'notify_new_partner' in request.POST
        settings.notify_doc_upload = 'notify_doc_upload' in request.POST
        settings.send_welcome_email = 'send_welcome_email' in request.POST
        
        # New Settings
        settings.require_otp_verification = 'require_otp_verification' in request.POST
        settings.homepage_hero_title = request.POST.get('homepage_hero_title', settings.homepage_hero_title)
        
        settings.save()
        messages.success(request, "System parameters synchronized successfully. Global state updated.")
        return redirect('admin_settings')
        
    notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')
    return render(request, 'admin/admin_settings.html', {
        'verification_notifications': notifications,
        'settings': settings
    })

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

@login_required
def export_reports_csv(request):
    if request.user.usertype != 'admin' and not request.user.is_superuser:
        messages.error(request, "Access denied")
        return redirect('index')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="travel_buddy_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Month', 'Revenue', 'New Users', 'Bookings'])

    today = date.today()
    for i in range(5, -1, -1):
        target_month = today.month - i
        target_year = today.year
        
        if target_month <= 0:
            target_month += 12
            target_year -= 1
            
        month_name = date(target_year, target_month, 1).strftime('%B %Y')
        
        revenue = Booking.objects.filter(
            status='CONFIRMED', 
            booking_date__year=target_year,
            booking_date__month=target_month
        ).aggregate(Sum('total_price'))['total_price__sum'] or 0
        
        new_users = Login.objects.filter(
            date_joined__year=target_year,
            date_joined__month=target_month
        ).count()
        
        bookings = Booking.objects.filter(
            booking_date__year=target_year,
            booking_date__month=target_month
        ).count()
        
        writer.writerow([month_name, revenue, new_users, bookings])

    return response

@login_required
def profile_redirect(request):
    """Redirect to the correct profile/dashboard based on user type"""
    if request.user.is_superuser or request.user.usertype == 'admin':
        return redirect('admin_dashboard')
    elif request.user.usertype == 'company':
        return redirect('company_profile')
    else:
        return redirect('user_dashboard')
