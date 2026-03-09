from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from .models import LoginLog

from django.utils import timezone
from datetime import timedelta

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR') # Fixed name
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    LoginLog.objects.create(
        user=user,
        username=user.username,
        ip_address=get_client_ip(request),
        status='Success',
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get('username', 'unknown')
    ip_address = get_client_ip(request) if request else None
    
    # Check for suspicious activity: > 3 failures in 15 minutes
    fifteen_mins_ago = timezone.now() - timedelta(minutes=15)
    
    # Check by IP
    failures_by_ip = LoginLog.objects.filter(
        ip_address=ip_address,
        status='Failure',
        timestamp__gte=fifteen_mins_ago
    ).count()
    
    # Check by Username
    failures_by_user = LoginLog.objects.filter(
        username=username,
        status='Failure',
        timestamp__gte=fifteen_mins_ago
    ).count()
    
    is_suspicious = (failures_by_ip >= 3 or failures_by_user >= 3)
    
    LoginLog.objects.create(
        username=username,
        ip_address=ip_address,
        status='Failure',
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else None,
        is_suspicious=is_suspicious
    )
