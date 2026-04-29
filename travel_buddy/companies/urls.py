from django.urls import path
from . import views

urlpatterns = [
    # Company registration
    path('company-register/', views.company_register_view, name='company_register'),
    path('company-verification/', views.verify_company, name='company_verification'),
    
    # Company dashboard and profile
    path('company-dashboard/', views.company_dashboard, name='company_dashboard'),
    path('company/profile/', views.company_profile, name='company_profile'),
    path('company/profile/edit/', views.edit_company_profile, name='edit_company_profile'),
    
    # Trip management
    path('company/create-trip/', views.create_trip, name='create_trip'),
    path('company/manage-trips/', views.manage_trips, name='manage_trips'),
    path('company/edit-trip/<int:trip_id>/', views.edit_trip, name='edit_trip'),
    path('company/delete-trip-image/<int:image_id>/', views.delete_trip_image, name='delete_trip_image'),
    path('company/delete-trip/<int:trip_id>/', views.delete_trip, name='delete_trip'),
    
    # Bookings and insights
    path('company/bookings/', views.view_bookings, name='view_bookings'),
    path('company/booking/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('company/trip-insights/<int:trip_id>/', views.trip_insights, name='trip_insights'),
    
    # Trip pause/unpause
    path('company/trip-pause/<int:trip_id>/', views.request_pause_trip, name='request_pause_trip'),
    path('company/trip-unpause/<int:trip_id>/', views.request_unpause_trip, name='request_unpause_trip'),
    
    # Trip communication
    path('trip-communication/<int:trip_id>/', views.trip_communication, name='trip_communication'),
    path('post-trip-update/<int:trip_id>/', views.post_trip_update, name='post_trip_update'),
    path('send-trip-message/<int:trip_id>/', views.send_trip_message, name='send_trip_message'),
    path('company/chat/', views.company_chat, name='company_chat'),
    
    # Document re-upload
    path('reupload-documents/', views.reupload_documents, name='reupload_documents'),
    
    # Company notifications
    path('company/mark-notification-read/<int:notification_id>/', views.mark_company_notification_read, name='mark_company_notification_read'),
    
    # Company reviews
    path('company/reviews/', views.company_reviews, name='company_reviews'),
]