class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Apply cache-control only to authenticated sessions to prevent back-button access to sensitive data
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            response['Vary'] = 'Cookie'
        return response

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Avoid circular import
        from app.models import SystemSetting
        from django.shortcuts import render
        from django.urls import resolve
        
        # Get settings
        settings = SystemSetting.get_settings()
        
        if settings.maintenance_mode:
            # Allow admins to bypass so they can turn it off!
            if request.user.is_authenticated and (request.user.is_superuser or request.user.usertype == 'admin'):
                return self.get_response(request)
            
            # Allow login page so admin can log in if they session expired
            url_name = resolve(request.path_info).url_name
            if url_name in ['login', 'logout', 'admin_settings']:
                return self.get_response(request)

            # Allow static files and media
            if request.path.startswith('/static/') or request.path.startswith('/media/'):
                return self.get_response(request)
                
            # For everyone else, show maintenance page
            return render(request, 'maintenance.html', status=503)
            
        return self.get_response(request)
