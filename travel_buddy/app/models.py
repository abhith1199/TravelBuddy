from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

class PasswordResetOTP(models.Model):
    user = models.ForeignKey('Login', on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # Check if the OTP is older than 10 minutes
        expiration_time = self.created_at + timezone.timedelta(minutes=10)
        return timezone.now() <= expiration_time and not self.is_used

    def __str__(self):
        return f"OTP for {self.user.username} - {'Used' if self.is_used else 'Valid'}"

class EmailVerificationOTP(models.Model):
    user = models.ForeignKey('Login', on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        # Check if the OTP is older than 15 minutes
        expiration_time = self.created_at + timezone.timedelta(minutes=15)
        return timezone.now() <= expiration_time and not self.is_used

    def __str__(self):
        return f"Email OTP for {self.user.username} - {'Used' if self.is_used else 'Valid'}"

class Login(AbstractUser):
    USER_TYPES = (
        ('traveler', 'Traveler'),
        ('company', 'Company'),
    )
    
    VERIFICATION_STATUS = (
        ('PENDING_VERIFICATION', 'Pending Verification'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    
    usertype = models.CharField(max_length=20, choices=USER_TYPES, default='traveler')
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='PENDING_VERIFICATION')
    
    # Traveler specific info
    gender = models.CharField(max_length=10, choices=[('MALE', 'Male'), ('FEMALE', 'Female'), ('OTHER', 'Other')], blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    interests = models.TextField(blank=True, null=True, help_text="Comma-separated list of interests")
    bio = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    # Company Information
    company_name = models.CharField(max_length=200, blank=True, null=True)
    registration_number = models.CharField(max_length=100, blank=True, null=True)
    company_phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    company_address = models.TextField(blank=True, null=True)
    established_year = models.IntegerField(blank=True, null=True)
    
    # Authorized Person Information
    contact_first_name = models.CharField(max_length=100, blank=True, null=True)
    contact_last_name = models.CharField(max_length=100, blank=True, null=True)
    contact_position = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Verification Details
    tourism_license_number = models.CharField(max_length=100, blank=True, null=True)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    business_type = models.CharField(max_length=100, blank=True, null=True)
    services_offered = models.TextField(blank=True, null=True)
    company_description = models.TextField(blank=True, null=True)
    license_document = models.FileField(upload_to='company_documents/licenses/', blank=True, null=True)
    government_id = models.FileField(upload_to='company_documents/government_ids/', blank=True, null=True)
    
    # Individual Document Status
    license_document_status = models.CharField(max_length=20, default='NOT_SUBMITTED', 
                                             choices=[('NOT_SUBMITTED', 'Not Submitted'), 
                                                    ('PENDING_REVIEW', 'Pending Review'), 
                                                    ('APPROVED', 'Approved'), 
                                                    ('REJECTED', 'Rejected')])
    government_id_status = models.CharField(max_length=20, default='NOT_SUBMITTED', 
                                          choices=[('NOT_SUBMITTED', 'Not Submitted'), 
                                                   ('PENDING_REVIEW', 'Pending Review'), 
                                                   ('APPROVED', 'Approved'), 
                                                   ('REJECTED', 'Rejected')])
    
    # Document Rejection Reasons
    license_rejection_reason = models.TextField(blank=True, null=True)
    government_id_rejection_reason = models.TextField(blank=True, null=True)
    
    # Verification Timestamps
    verification_submitted_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    view_password = models.CharField(max_length=100, blank=True, null=True)
    email_verified = models.BooleanField(default=False)

    # Razorpay Payment Gateway
    razorpay_key_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_key_secret = models.CharField(max_length=100, blank=True, null=True)
    
    # Company Tier
    tier = models.CharField(max_length=20, default='NEWBIE', choices=[('NEWBIE', 'Newbie'), ('PRO', 'Pro'), ('ELITE', 'Elite Operator')])
    
    def __str__(self):
        return self.username
    
    def is_company_verified(self):
        """Check if company is verified and approved"""
        return self.usertype == 'company' and self.verification_status == 'APPROVED'
    
    def needs_verification(self):
        """Check if company needs to complete verification"""
        return self.usertype == 'company' and self.verification_status in ['PENDING', 'REJECTED']

    @property
    def social_activities_list(self):
        """Parse social activities as a list, split by newline or comma"""
        if self.social_activities:
            # Split by newline first, then by comma if needed
            activities = [a.strip() for a in self.social_activities.replace('\r', '').split('\n') if a.strip()]
            if not activities and ',' in self.social_activities:
                activities = [a.strip() for a in self.social_activities.split(',') if a.strip()]
            return activities
        return []

    def get_company_rating(self):
        """Calculate average rating across all trips for the company"""
        if self.usertype != 'company':
            return 0
        from django.db.models import Avg
        from .models import Review
        avg_rating = Review.objects.filter(trip__company=self).aggregate(Avg('rating_overall'))['rating_overall__avg']
        return round(avg_rating, 2) if avg_rating else 0

        return self.usertype == 'company' and self.verification_status == 'PENDING_VERIFICATION'

    def get_interests_list(self):
        """Return interests as a list"""
        if self.interests:
            return [x.strip() for x in self.interests.split(',')]
        return []

    @property
    def has_unread_company_chats(self):
        if self.usertype != 'company':
            return False
        for trip in self.trips.all():
            if trip.has_unread_company_messages:
                return True
        return False
        
    @property
    def has_unread_traveler_chats(self):
        if self.usertype != 'traveler':
            return False
        for booking in self.bookings.all():
            if booking.has_unread_messages:
                return True
        return False


class AdminNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('VERIFICATION_SUBMITTED', 'Verification Submitted'),
        ('VERIFICATION_APPROVED', 'Verification Approved'),
        ('VERIFICATION_REJECTED', 'Verification Rejected'),
        ('DOCUMENT_REJECTED', 'Document Rejected'),
        ('DOCUMENT_APPROVED', 'Document Approved'),
        ('ACTION_REQUIRED', 'Action Required'),
        ('NEW_COMPANY', 'New Company'),
        ('TRIP_STARTING', 'Trip Starting'),
        ('TRIP_ONGOING', 'Trip Ongoing'),
        ('TRIP_COMPLETED', 'Trip Completed'),
        ('TRIP_CANCELLED', 'Trip Cancelled'),
        ('TRIP_PAUSE_REQUEST', 'Trip Pause Request'),
    ]
    
    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    company = models.ForeignKey('Login', on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Document-specific fields
    document_type = models.CharField(max_length=20, blank=True, null=True, 
                                    choices=[('LICENSE', 'License Document'), 
                                           ('GOVERNMENT_ID', 'Government ID')])
    
    def __str__(self):
        return f"{self.type} - {self.title}"

class TravelerNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('BOOKING_CONFIRMED', 'Booking Confirmed'),
        ('BOOKING_CANCELLED', 'Booking Cancelled'),
        ('TRIP_STARTING_SOON', 'Trip Starting Soon'),
        ('TRIP_ONGOING', 'Trip is Ongoing'),
        ('TRIP_COMPLETED', 'Trip Completed'),
        ('TRIP_UPDATE', 'Trip Update'),
        ('TRIP_CANCELLED', 'Trip Cancelled'),
        ('REVIEW_REMINDER', 'Review Reminder'),
    ]
    
    user = models.ForeignKey('Login', on_delete=models.CASCADE, related_name='notifications')
    trip = models.ForeignKey('Trip', on_delete=models.CASCADE, null=True, blank=True)
    booking = models.ForeignKey('Booking', on_delete=models.CASCADE, null=True, blank=True)
    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} - {self.title}"


class Trip(models.Model):
    # Status Choices
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved & Active'),
        ('REJECTED', 'Rejected'),
        ('SUSPENDED', 'Suspended'),
        ('PAUSED', 'Paused by Company'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    )

    # Vibe Tags (Crowd/Style)
    VIBE_CHOICES = (
        ('ADVENTURE', 'Adventure & Thrill'),
        ('CHILL', 'Chill & Relax'),
        ('PARTY', 'Party Crowd'),
        ('SPIRITUAL', 'Spiritual & Wellness'),
        ('SOLO_FRIENDLY', 'Solo Friendly'),
        ('DIGITAL_DETOX', 'Digital Detox'),
        ('ROMANTIC', 'Couples/Romantic'),
        ('CULTURE', 'Culture & History'),
        ('EXPLORING', 'Exploring & Sightseeing'),
        ('TEAM_BUILDING', 'Team Building'),
        ('CORPORATE', 'Corporate Retreat'),
        ('WEEKEND', 'Weekend Getaway'),
        ('NATURE', 'Nature & Wildlife'),
    )

    # Gender Restrictions
    GENDER_CHOICES = (
        ('ANY', 'Mixed Group (Any)'),
        ('FEMALE_ONLY', 'Female Only'),
        ('MALE_ONLY', 'Male Only'),
        ('COUPLES_ONLY', 'Couples Only'),
    )

    company = models.ForeignKey(Login, on_delete=models.CASCADE, related_name='trips')
    
    # Basic Info
    title = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Schedule
    start_date = models.DateField()
    end_date = models.DateField()
    duration_days = models.IntegerField(help_text="Duration in days")
    
    # Vibe & Categorization
    vibe_tag = models.CharField(max_length=50, choices=VIBE_CHOICES)
    trip_type = models.CharField(max_length=100)  # e.g., Trekking, Beach, etc.
    
    # Audience Constraints
    age_min = models.IntegerField(default=18)
    age_max = models.IntegerField(default=60)
    gender_restriction = models.CharField(max_length=20, choices=GENDER_CHOICES, default='ANY')
    max_capacity = models.IntegerField()
    current_bookings = models.IntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0) # For Analytics
    
    # Itinerary
    itinerary_details = models.TextField(help_text="Detailed day-wise itinerary")
    social_activities = models.TextField(help_text="Ice-breakers, games, etc.", blank=True, null=True)
    
    # Pause Control
    is_paused = models.BooleanField(default=False)
    is_pause_requested = models.BooleanField(default=False)
    
    # Admin Control
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    company_chat_last_read = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.destination})"

    @property
    def booking_percentage(self):
        if self.max_capacity > 0:
            return min(int((self.current_bookings / self.max_capacity) * 100), 100)
        return 0
    
    def get_trust_score(self):
        """Calculate trust score from average of all ratings"""
        from django.db.models import Avg
        avg_rating = Review.objects.filter(trip=self).aggregate(Avg('rating_overall'))['rating_overall__avg']
        return round(avg_rating, 2) if avg_rating else 0

    @property
    def vibe_display(self):
        return dict(self.VIBE_CHOICES).get(self.vibe_tag, self.vibe_tag)
        
    @property
    def has_unread_company_messages(self):
        if self.status == 'EXPIRED':
            return False
            
        last_message = self.chat_messages.last()
        if not last_message:
            return False
            
        if last_message.sender == self.company:
            return False
            
        if not self.company_chat_last_read:
            return True
        return last_message.created_at > self.company_chat_last_read

class TripImage(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='trip_images/')
    caption = models.CharField(max_length=200, blank=True, null=True)
    is_cover = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.trip.title}"

class Booking(models.Model):
    BOOKING_STATUS = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    )

    traveler = models.ForeignKey(Login, on_delete=models.CASCADE, related_name='bookings')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='PENDING')
    num_people = models.PositiveIntegerField(default=1)
    num_males = models.PositiveIntegerField(default=0)
    num_females = models.PositiveIntegerField(default=0)
    num_others = models.PositiveIntegerField(default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    booking_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    traveler_chat_last_read = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.traveler.username} - {self.trip.title}"
        
    @property
    def has_unread_messages(self):
        if self.trip.status == 'EXPIRED':
            return False
            
        last_message = self.trip.chat_messages.last()
        if not last_message:
            return False
            
        if last_message.sender == self.traveler:
            return False
            
        if not self.traveler_chat_last_read:
            return True
        return last_message.created_at > self.traveler_chat_last_read

class TripUpdate(models.Model):
    UPDATE_TYPES = (
        ('MEETING_POINT', 'Meeting Point'),
        ('PACKING_LIST', 'Packing List'),
        ('SAFETY', 'Safety Instructions'),
        ('GENERAL', 'General Announcement'),
    )
    
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='updates')
    author = models.ForeignKey(Login, on_delete=models.CASCADE)
    update_type = models.CharField(max_length=20, choices=UPDATE_TYPES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.update_type} for {self.trip.title}"

class TripChat(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(Login, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message from {self.sender.username} in {self.trip.title}"

class Review(models.Model):
    trip = models.ForeignKey('Trip', on_delete=models.CASCADE, related_name='reviews')
    booking = models.OneToOneField('Booking', on_delete=models.CASCADE)
    reviewer = models.ForeignKey(Login, on_delete=models.CASCADE)
    
    # Ratings (1-5)
    rating_overall = models.PositiveIntegerField(default=5)
    rating_social_vibe = models.PositiveIntegerField(default=5) # For "Social Vibe" requirement
    rating_logistics = models.PositiveIntegerField(default=5) # For "Logistics" requirement
    rating_safety = models.PositiveIntegerField(default=5) # For "Safety" requirement
    
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review for {self.trip.title} by {self.reviewer.username}"

class Report(models.Model):
    REPORT_REASONS = (
        ('TOXIC_BEHAVIOR', 'Toxic Behavior'),
        ('SCAM', 'Scam/Fraud'),
        ('SAFETY', 'Safety Violation'),
        ('OTHER', 'Other'),
    )
    
    reporter = models.ForeignKey(Login, on_delete=models.CASCADE, related_name='filed_reports')
    
    # Generic relation to report User, Company, or Trip
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    reported_object = GenericForeignKey('content_type', 'object_id')
    
    reason = models.CharField(max_length=50, choices=REPORT_REASONS)
    details = models.TextField()
    status = models.CharField(max_length=20, default='PENDING', choices=[('PENDING', 'Pending'), ('RESOLVED', 'Resolved'), ('DISMISSED', 'Dismissed')])
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Report {self.id} - {self.reason}"

class Wallet(models.Model):
    company = models.OneToOneField(Login, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Wallet for {self.company.company_name}"

class Transaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=20, choices=[('CREDIT', 'Credit'), ('DEBIT', 'Debit')])
    created_at = models.DateTimeField(auto_now_add=True)

class SystemSetting(models.Model):
    """Global configuration for the Travel Buddy platform"""
    # General
    maintenance_mode = models.BooleanField(default=False)
    allow_registrations = models.BooleanField(default=True)
    platform_name = models.CharField(max_length=100, default="Travel Buddy")
    support_email = models.EmailField(default="support@travelbuddy.com")
    
    # Financial
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    
    # Notifications
    notify_new_partner = models.BooleanField(default=True)
    notify_doc_upload = models.BooleanField(default=True)
    send_welcome_email = models.BooleanField(default=True)
    
    # Security/Demo
    require_otp_verification = models.BooleanField(default=True)
    
    # Homepage Customization
    homepage_hero_title = models.CharField(max_length=200, default="Find Your Perfect Group Adventure")
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Global System Settings"

    @classmethod
    def get_settings(cls):
        """Helper to get or create the single settings record"""
        settings, created = cls.objects.get_or_create(id=1)
        return settings
