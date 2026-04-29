from django.contrib.messages import get_messages
from .models import AdminNotification, Login, TravelerNotification

def notifications(request):
    """
    Context processor to provide notification data for templates
    """
    if request.user.is_authenticated and request.user.is_superuser:
        # Admin notifications
        notifications = AdminNotification.objects.filter(is_read=False).order_by('-created_at')[:5]
        unread_count = AdminNotification.objects.filter(is_read=False).count()
        
        # Task-based counts (Work Management)
        from .models import Trip, Report
        pending_verifications_count = Login.objects.filter(usertype='company', verification_status='PENDING_VERIFICATION').count()
        pending_trips_count = Trip.objects.filter(status='PENDING_REVIEW').count()
        pending_reports_count = Report.objects.filter(status='PENDING', is_read=False).count()
        
        return {
            'notifications': notifications,
            'unread_count': unread_count,
            'pending_verifications_count': pending_verifications_count,
            'pending_trips_count': pending_trips_count,
            'pending_reports_count': pending_reports_count,
        }
    elif request.user.is_authenticated and request.user.usertype == 'company':
        # Company notifications
        company_notifications = AdminNotification.objects.filter(
            company=request.user,
            is_read=False
        ).order_by('-created_at')[:5]
        company_unread_count = AdminNotification.objects.filter(
            company=request.user,
            is_read=False
        ).count()
        
        # Action required notifications (document rejections, etc.)
        action_required_notifications = AdminNotification.objects.filter(
            company=request.user,
            type__in=['DOCUMENT_REJECTED', 'ACTION_REQUIRED'],
            is_read=False
        )
        
        return {
            'company_notifications': company_notifications,
            'company_unread_count': company_unread_count,
            'action_required_notifications': action_required_notifications,
        }
    elif request.user.is_authenticated and request.user.usertype == 'traveler':
        # Traveler notifications
        traveler_notifications = TravelerNotification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by('-created_at')[:5]
        
        return {
            'traveler_notifications': traveler_notifications,
            'traveler_unread_count': traveler_notifications.count(),
        }
    
    return {}

def global_settings(request):
    """Provides global system settings to all templates"""
    from .models import SystemSetting
    return {
        'site_settings': SystemSetting.get_settings()
    }
