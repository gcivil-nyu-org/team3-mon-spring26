from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_http_methods, require_POST
from .forms import (
    UserRegisterForm,
    UserLoginForm,
    RestaurantProfileForm,
    RestaurantAvailabilityForm,
    RestaurantActivationForm,
    RestaurantPhotoForm,
)
from .models import Restaurant, RestaurantPhoto, RestaurantSearch


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


def map_view(request):
    """
    Render interactive restaurant map page with filters and server-provided options.
    """
    restaurants = Restaurant.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    boroughs = sorted(
        {
            borough.strip().title()
            for borough in restaurants.values_list("borough", flat=True)
            if borough
        }
    )

    search = request.GET.get("search", "").strip()
    borough = request.GET.get("borough", "").strip()
    min_score = request.GET.get("min_score", "").strip()
    max_score = request.GET.get("max_score", "").strip()
    cuisine = request.GET.get("cuisine", "").strip()
    sort_by = request.GET.get("sort_by", "score_desc").strip()

    if search:
        restaurants = restaurants.filter(
            Q(name__icontains=search)
            | Q(street__icontains=search)
            | Q(zip_code__icontains=search)
            | Q(borough__icontains=search)
        )
    if borough:
        restaurants = restaurants.filter(borough__iexact=borough)
    if cuisine:
        restaurants = restaurants.filter(cuisine_tags__icontains=cuisine)
    if min_score:
        try:
            restaurants = restaurants.filter(composite_score__gte=float(min_score))
        except ValueError:
            min_score = ""
    if max_score:
        try:
            restaurants = restaurants.filter(composite_score__lte=float(max_score))
        except ValueError:
            max_score = ""

    cuisines = set()
    for row in restaurants.values_list("cuisine_tags", flat=True):
        for value in row or []:
            cuisines.add(str(value).strip())

    context = {
        "title": "Restaurant Map",
        "search": search,
        "borough": borough,
        "min_score": min_score,
        "max_score": max_score,
        "cuisine": cuisine,
        "sort_by": sort_by,
        "boroughs": boroughs,
        "cuisines": sorted(filter(None, (item.title() for item in cuisines))),
        "restaurant_count": restaurants.count(),
    }
    return render(request, "nomz/map.html", context)


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


# ============================================================================
# RESTAURANT PROFILE MANAGEMENT VIEWS
# ============================================================================


def is_restaurant_owner(user):
    """Helper function to check if user is a restaurant owner"""
    return hasattr(user, 'userprofile') and user.userprofile.role == 'restaurant'


@login_required(login_url='landing')
def restaurant_profile(request):
    """
    View restaurant owner's profile page
    Shows restaurant details, photos, and status
    """
    if not is_restaurant_owner(request.user):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    try:
        restaurant = Restaurant.objects.get(owner=request.user)
    except Restaurant.DoesNotExist:
        restaurant = None
    
    context = {
        'title': 'Restaurant Profile',
        'restaurant': restaurant,
        'has_restaurant': restaurant is not None,
    }
    return render(request, 'nomz/restaurant_profile.html', context)


@login_required(login_url='landing')
@require_http_methods(["GET", "POST"])
def create_restaurant_profile(request):
    """
    Create a new restaurant profile
    Only for restaurant owners without a profile yet
    """
    if not is_restaurant_owner(request.user):
        messages.error(request, 'You do not have permission to create a restaurant profile.')
        return redirect('dashboard')
    
    # Check if user already has a restaurant
    if Restaurant.objects.filter(owner=request.user).exists():
        messages.info(request, 'You already have a restaurant profile.')
        return redirect('restaurant_profile')
    
    if request.method == 'POST':
        form = RestaurantProfileForm(request.POST)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.owner = request.user
            restaurant.save()
            messages.success(request, 'Restaurant profile created successfully!')
            return redirect('restaurant_profile')
    else:
        form = RestaurantProfileForm()
    
    context = {
        'title': 'Create Restaurant Profile',
        'form': form,
        'is_create': True,
    }
    return render(request, 'nomz/restaurant_form.html', context)


@login_required(login_url='landing')
@require_http_methods(["GET", "POST"])
def edit_restaurant_profile(request):
    """
    Edit existing restaurant profile
    Handles updates to description, hours, cuisine, and price range
    """
    if not is_restaurant_owner(request.user):
        messages.error(request, 'You do not have permission to edit a restaurant profile.')
        return redirect('dashboard')
    
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    
    if request.method == 'POST':
        form = RestaurantProfileForm(request.POST, instance=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Restaurant profile updated successfully!')
            return redirect('restaurant_profile')
    else:
        form = RestaurantProfileForm(instance=restaurant)
    
    context = {
        'title': 'Edit Restaurant Profile',
        'form': form,
        'restaurant': restaurant,
        'is_create': False,
    }
    return render(request, 'nomz/restaurant_form.html', context)


@login_required(login_url='landing')
@require_http_methods(["GET", "POST"])
def manage_availability(request):
    """
    Manage restaurant availability (temporary closure)
    """
    if not is_restaurant_owner(request.user):
        messages.error(request, 'You do not have permission to manage availability.')
        return redirect('dashboard')
    
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    
    if request.method == 'POST':
        form = RestaurantAvailabilityForm(request.POST, instance=restaurant)
        if form.is_valid():
            form.save()
            if restaurant.is_temporarily_unavailable:
                messages.success(request, 'Restaurant marked as temporarily unavailable.')
            else:
                messages.success(request, 'Restaurant availability updated.')
            return redirect('restaurant_profile')
    else:
        form = RestaurantAvailabilityForm(instance=restaurant)
    
    context = {
        'title': 'Manage Availability',
        'form': form,
        'restaurant': restaurant,
    }
    return render(request, 'nomz/manage_availability.html', context)


@login_required(login_url='landing')
@require_http_methods(["GET", "POST"])
def manage_activation(request):
    """
    Activate or deactivate restaurant profile
    """
    if not is_restaurant_owner(request.user):
        messages.error(request, 'You do not have permission to manage activation.')
        return redirect('dashboard')
    
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    
    if request.method == 'POST':
        form = RestaurantActivationForm(request.POST, instance=restaurant)
        if form.is_valid():
            form.save()
            if restaurant.is_active:
                messages.success(request, 'Restaurant profile is now visible to customers.')
            else:
                messages.warning(request, 'Restaurant profile has been deactivated. It is no longer visible to customers.')
            return redirect('restaurant_profile')
    else:
        form = RestaurantActivationForm(instance=restaurant)
    
    context = {
        'title': 'Manage Profile Status',
        'form': form,
        'restaurant': restaurant,
    }
    return render(request, 'nomz/manage_activation.html', context)


@login_required(login_url='landing')
@require_http_methods(["GET", "POST"])
def upload_photo(request):
    """
    Upload a new restaurant photo
    """
    if not is_restaurant_owner(request.user):
        messages.error(request, 'You do not have permission to upload photos.')
        return redirect('dashboard')
    
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    
    if request.method == 'POST':
        form = RestaurantPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.restaurant = restaurant
            photo.save()
            messages.success(request, 'Photo uploaded successfully!')
            return redirect('restaurant_photos')
    else:
        form = RestaurantPhotoForm()
    
    context = {
        'title': 'Upload Photo',
        'form': form,
        'restaurant': restaurant,
    }
    return render(request, 'nomz/upload_photo.html', context)


@login_required(login_url='landing')
def restaurant_photos(request):
    """
    View and manage all restaurant photos
    """
    if not is_restaurant_owner(request.user):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    photos = restaurant.photos.all()
    
    context = {
        'title': 'Manage Photos',
        'restaurant': restaurant,
        'photos': photos,
    }
    return render(request, 'nomz/restaurant_photos.html', context)


@login_required(login_url='landing')
@require_POST
def delete_photo(request, photo_id):
    """
    Delete a restaurant photo
    """
    if not is_restaurant_owner(request.user):
        return HttpResponseForbidden('Permission denied')
    
    photo = get_object_or_404(RestaurantPhoto, id=photo_id)
    
    if photo.restaurant.owner != request.user:
        return HttpResponseForbidden('Permission denied')
    
    photo.delete()
    messages.success(request, 'Photo deleted successfully!')
    return redirect('restaurant_photos')


@login_required(login_url='landing')
@require_POST
def set_primary_photo(request, photo_id):
    """
    Set a photo as the primary (main) photo for the restaurant
    """
    if not is_restaurant_owner(request.user):
        return HttpResponseForbidden('Permission denied')
    
    photo = get_object_or_404(RestaurantPhoto, id=photo_id)
    
    if photo.restaurant.owner != request.user:
        return HttpResponseForbidden('Permission denied')
    
    # Set this as primary (the save method will handle unsetting others)
    photo.is_primary = True
    photo.save()
    messages.success(request, 'Primary photo updated!')
    return redirect('restaurant_photos')


@login_required(login_url='landing')
def restaurant_search(request):
    query = request.GET.get('q', '')
    neighborhood = request.GET.get('neighborhood', '')
    
    # Start with all restaurants
    results = RestaurantSearch.objects.all()
    
    # Apply keyword search (Name or Description)
    if query:
        results = results.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(cuisine__icontains=query)
        )
    
    # Apply neighborhood filter
    if neighborhood:
        results = results.filter(neighborhood__iexact=neighborhood)
        
    # Get unique neighborhoods for the dropdown filter
    all_neighborhoods = RestaurantSearch.objects.values_list('neighborhood', flat=True).distinct()

    return render(request, 'nomz/search_results.html', {
        'results': results,
        'query': query,
        'neighborhood': neighborhood,
        'all_neighborhoods': all_neighborhoods
    })
