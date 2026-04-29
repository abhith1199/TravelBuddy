from django.urls import path
from . import views

urlpatterns = [
    # Traveler authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    
    # Email Verification (OTP Flow)
    path('verify-email-otp/', views.verify_email_otp, name='verify_email_otp'),
    path('resend-verification-otp/', views.resend_verification_otp, name='resend_verification_otp'),

    # Password Reset (OTP Flow)
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password_otp, name='reset_password_otp'),
    
    # Traveler dashboard and profile
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('user/profile/edit/', views.edit_user_profile, name='edit_user_profile'),
    path('user/settings/', views.user_settings, name='user_settings'),
    path('user/change-username/', views.change_username, name='change_username'),
    path('user/change-password/', views.change_password, name='change_password'),
    
    # Trip browsing and booking
    path('browse-trips/', views.browse_trips, name='browse_trips'),
    path('trip/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('trip/<int:trip_id>/book/', views.book_trip, name='book_trip'),
    path('booking/confirmation/<int:booking_id>/', views.booking_confirmation, name='booking_confirmation'),
    path('booking/payment/<int:booking_id>/', views.payment_mock, name='payment_mock'),
    path('booking/success/<int:booking_id>/', views.booking_success, name='booking_success'),
    
    # Traveler bookings and reviews
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('review/submit/<int:booking_id>/', views.submit_review, name='submit_review'),
    
    # Traveler notifications
    path('traveler/mark-notification-read/<int:notification_id>/', views.mark_traveler_notification_read, name='mark_traveler_notification_read'),
    
    # Profile redirect
    path('profile/', views.profile_redirect, name='profile'),
    
    # Receipt download
    path('download-receipt/<int:booking_id>/', views.download_receipt, name='download_receipt'),
]