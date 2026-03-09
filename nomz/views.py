from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .forms import UserRegisterForm, UserLoginForm


def landing_page(request):
    """
    Landing page - entry point for the application
    Shows Sign Up and Login options
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    context = {
        'title': 'Welcome to Nomz',
    }
    return render(request, 'nomz/landing.html', context)


def home(request):
    """
    Home page view - displays different content based on authentication status
    """
    context = {
        'title': 'Home',
    }
    return render(request, 'nomz/home.html', context)


def health_check(request):
    """
    Lightweight health endpoint for ELB/EB health checks.
    Must return HTTP 200 quickly and without auth redirects.
    Compatible with develop's HealthCheckPath: /health/
    """
    return JsonResponse({"status": "ok"}, status=200)


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created successfully for {username}!')
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserRegisterForm()
    
    context = {'form': form, 'title': 'Register'}
    return render(request, 'nomz/register.html', context)


@require_http_methods(["GET", "POST"])
def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
    else:
        form = UserLoginForm()
    
    context = {'form': form, 'title': 'Login'}
    return render(request, 'nomz/login.html', context)


@login_required(login_url='landing')
def dashboard(request):
    """
    Dashboard dynamically routes based on the database profile
    """
    # 1. Check if they are a built-in Django Admin
    if request.user.is_superuser or request.user.is_staff:
        role = 'admin'
    # 2. Check their profile in the database
    elif hasattr(request.user, 'userprofile'):
        role = request.user.userprofile.role
    # 3. Fallback
    else:
        role = 'diner' 

    context = {
        'title': 'Dashboard',
        'user': request.user,
        'role': role,
    }
    
    if role == 'restaurant':
        return render(request, 'nomz/restaurant_dashboard.html', context)
    elif role == 'admin':
        return render(request, 'nomz/admin_dashboard.html', context)
    else:
        return render(request, 'nomz/user_dashboard.html', context)


@login_required(login_url='landing')
@require_http_methods(["POST"])
def user_logout(request):
    """
    User logout view
    Logs out the user and redirects to landing page
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('landing')
