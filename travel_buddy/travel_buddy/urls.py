"""
URL configuration for travel_buddy project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from app import views as app_views
from travelers import views as traveler_views
from companies import views as company_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Home page
    path('', traveler_views.index, name='index'),
    
    # Include traveler URLs
    path('', include('travelers.urls')),
    
    # Include company URLs
    path('', include('companies.urls')),
    
    # Admin URLs from app
    path('admin-dashboard/', app_views.admin_dashboard, name='admin_dashboard'),
    path('user/change-username/', app_views.change_username, name='change_username'),
    path('user/change-password/', app_views.change_password, name='change_password'),
    path('company-dashboard/', app_views.company_dashboard, name='company_dashboard'),
    
    # Admin notification endpoints
    path('admin/mark-notification-read/<int:notification_id>/', app_views.mark_notification_read, name='mark_notification_read'),
    path('admin/mark-all-notifications-read/', app_views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # Admin - Company Verification & Management
    path('admin/verification/', app_views.admin_verification_management, name='admin_verification_management'),
    path('approve-verification/<int:company_id>/', app_views.approve_company_verification, name='approve_company_verification'),
    path('reject-verification/<int:company_id>/', app_views.reject_company_verification, name='reject_company_verification'),
    path('delete-company/<int:company_id>/', app_views.delete_company, name='delete_company'),
    
    # Data Safety & Moderation
    path('admin/safety/', app_views.admin_safety_dashboard, name='admin_safety_dashboard'),
    path('report/<str:content_type_str>/<int:object_id>/', app_views.submit_report, name='submit_report'),
    
    # Admin - User Management
    path('admin/user-management/', app_views.admin_user_management, name='admin_user_management'),
    path('admin/user/<int:user_id>/toggle-status/', app_views.admin_toggle_user_status, name='admin_toggle_user_status'),
    path('admin/user/<int:user_id>/delete/', app_views.admin_delete_user, name='admin_delete_user'),
    path('admin/get-user-details/<int:user_id>/', app_views.admin_get_user_details, name='admin_get_user_details'),
    
    # Admin - Trip Management
    path('admin/trip-management/', app_views.admin_trip_management, name='admin_trip_management'),
    path('admin/trip/<int:trip_id>/audit/', app_views.trip_audit, name='trip_audit'),
    path('admin/trip/<int:trip_id>/approve/', app_views.approve_trip, name='approve_trip'),
    path('admin/trip/<int:trip_id>/reject/', app_views.reject_trip, name='reject_trip'),
    path('admin/trip/<int:trip_id>/approve-pause/', app_views.admin_approve_pause, name='admin_approve_pause'),
    path('admin/trip/<int:trip_id>/reject-pause/', app_views.admin_reject_pause, name='admin_reject_pause'),
    path('admin/trip/<int:trip_id>/suspend/', app_views.suspend_trip, name='suspend_trip'),
    path('admin/trip/<int:trip_id>/unsuspend/', app_views.unsuspend_trip, name='unsuspend_trip'),
    path('admin/trip/<int:trip_id>/reverse/', app_views.reverse_approval, name='reverse_approval'),
    path('admin/trip/<int:trip_id>/rereview/', app_views.rereview_trip, name='rereview_trip'),
    path('admin/trip/<int:trip_id>/delete/', app_views.admin_delete_trip, name='admin_delete_trip'),
    
    # Admin - Payment Management
    path('admin/payment-management/', app_views.admin_payment_management, name='admin_payment_management'),
    
    # Admin - Review Management
    path('admin/reviews/', app_views.admin_review_management, name='admin_review_management'),
    path('admin/review/<int:review_id>/delete/', app_views.delete_review, name='delete_review'),
    
    # Admin - Reports & Analytics
    path('admin/reports/', app_views.admin_reports_analytics, name='admin_reports_analytics'),
    path('admin/reports/export/', app_views.export_reports_csv, name='export_reports_csv'),
    path('admin/users/export/', app_views.export_users_csv, name='admin_export_users'),
    
    # Admin - Settings
    path('admin/settings/', app_views.admin_settings, name='admin_settings'),
    
    # Django Admin (MUST be after custom admin URLs)
    path('admin/', admin.site.urls),
    
    # Company features (require verification)
    path('company/create-trip/', company_views.create_trip, name='create_trip'),
    path('company/manage-trips/', company_views.manage_trips, name='manage_trips'),
    path('company/edit-trip/<int:trip_id>/', company_views.edit_trip, name='edit_trip'),
    path('company/delete-trip-image/<int:image_id>/', company_views.delete_trip_image, name='delete_trip_image'),
    path('company/delete-trip/<int:trip_id>/', company_views.delete_trip, name='delete_trip'),
    path('company/bookings/', company_views.view_bookings, name='view_bookings'),
    path('company/booking/<int:booking_id>/', company_views.booking_detail, name='booking_detail'),
    path('company/trip-insights/<int:trip_id>/', company_views.trip_insights, name='trip_insights'),
    path('company/trip-insights/<int:trip_id>/export/', company_views.export_traveler_manifest, name='export_traveler_manifest'),
    path('company/trip-pause/<int:trip_id>/', company_views.request_pause_trip, name='request_pause_trip'),
    path('company/trip-unpause/<int:trip_id>/', company_views.request_unpause_trip, name='request_unpause_trip'),
    path('trip-communication/<int:trip_id>/', company_views.trip_communication, name='trip_communication'),
    path('post-trip-update/<int:trip_id>/', company_views.post_trip_update, name='post_trip_update'),
    path('send-trip-message/<int:trip_id>/', company_views.send_trip_message, name='send_trip_message'),
    path('company/chat/', company_views.company_chat, name='company_chat'),
    path('company/profile/', company_views.company_profile, name='company_profile'),
    path('company/profile/edit/', company_views.edit_company_profile, name='edit_company_profile'),
    path('document-review/<int:company_id>/', company_views.document_review, name='document_review'),
    path('approve-document/<int:company_id>/<str:document_type>/', company_views.approve_document, name='approve_document'),
    path('reject-document/<int:company_id>/<str:document_type>/', company_views.reject_document, name='reject_document'),
    
    # Company document re-upload
    path('reupload-documents/', company_views.reupload_documents, name='reupload_documents'),
    path('my-bookings/', company_views.my_bookings, name='my_bookings'),
    path('review/submit/<int:booking_id>/', company_views.submit_review, name='submit_review'),
    path('profile/', company_views.profile_redirect, name='profile'),
    
    # Company notification endpoints
    path('company/mark-notification-read/<int:notification_id>/', company_views.mark_company_notification_read, name='mark_company_notification_read'),
    # Traveler notification endpoints
    path('traveler/mark-notification-read/<int:notification_id>/', traveler_views.mark_traveler_notification_read, name='mark_traveler_notification_read'),
]

# Serve media and static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.BASE_DIR / 'static')
