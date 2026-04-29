from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Login

@login_required
def admin_get_user_details(request, user_id):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    try:
        user = Login.objects.get(id=user_id)
        
        data = {
            'username': user.username,
            'email': user.email,
            'date_joined': user.date_joined.strftime('%Y-%m-%d'),
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never',
            'is_active': user.is_active,
            'usertype': user.get_usertype_display(),
        }
        
        if user.usertype == 'company':
            data.update({
                'company_name': user.company_name,
                'registration_number': user.registration_number,
                'company_phone': user.company_phone,
                'website': user.website,
                'company_address': user.company_address,
                'established_year': user.established_year,
                'contact_first_name': user.contact_first_name,
                'contact_last_name': user.contact_last_name,
                'contact_position': user.contact_position,
                'contact_phone': user.contact_phone,
                'verification_status': user.get_verification_status_display(),
                'license_document_status': user.get_license_document_status_display(),
                'government_id_status': user.get_government_id_status_display(),
                'license_dict_url': user.license_document.url if user.license_document else None,
                'government_id_url': user.government_id.url if user.government_id else None,
            })
            
        return JsonResponse(data)
        
    except Login.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
