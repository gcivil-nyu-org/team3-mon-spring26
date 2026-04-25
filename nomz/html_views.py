"""
HTML Template Views for nomz
Replaces React SPA with Django-rendered HTML templates
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required

# ==============================================================================
# PUBLIC PAGES (No authentication required)
# ==============================================================================


def opening_screen(request):
    """Opening splash screen with animated 'nomz' logo"""
    return render(request, "nomz/opening.html")


def home(request):
    """Marketing/landing page"""
    return render(request, "nomz/home.html")


# ==============================================================================
# AUTHENTICATION PAGES
# ==============================================================================


def signin(request):
    """Sign in page"""
    # Check if user came from admin login
    admin_mode = request.GET.get("admin") == "true"
    return render(request, "nomz/auth/signin.html", {"admin_mode": admin_mode})


def signup(request):
    """Sign up / registration page"""
    return render(request, "nomz/auth/signup.html")


def two_factor_auth(request):
    """2FA verification page"""
    return render(request, "nomz/auth/two_factor.html")


def password_reset(request):
    """Password reset request page (step 1/4)"""
    return render(request, "nomz/auth/password_reset.html")


def password_reset_done(request):
    """Password reset email sent confirmation (step 2/4)"""
    return render(request, "nomz/auth/password_reset_done.html")


def password_reset_confirm(request):
    """Password reset confirmation page (step 3/4)"""
    # Extract uidb64 and token from URL if needed
    return render(request, "nomz/auth/password_reset_confirm.html")


def password_reset_complete(request):
    """Password reset complete page (step 4/4)"""
    return render(request, "nomz/auth/password_reset_complete.html")


def logout_view(request):
    """Logout - handled by JavaScript but this provides fallback"""
    from django.contrib.auth import logout

    logout(request)
    return redirect("home")


# ==============================================================================
# DASHBOARD / ROUTING
# ==============================================================================


@login_required
def dashboard(request):
    """
    Smart dashboard router:
    - Admin users → /nomz-admin/
    - Restaurant owners → /restaurant-profile/
    - Diners → UserHome dashboard
    """
    user = request.user

    if user.is_staff:
        # Render directly for compatibility with tests expecting a 200 dashboard response.
        return render(request, "nomz/admin/dashboard.html")

    # Check if user is restaurant owner
    try:
        if hasattr(user, "userprofile") and user.userprofile.role == "restaurant":
            return render(request, "nomz/restaurant/profile.html")
    except Exception:
        pass

    # Default: diner dashboard
    return render(request, "nomz/diner/dashboard.html", {"username": user.username})


# ==============================================================================
# DINER PAGES
# ==============================================================================


@login_required
def map_view(request):
    """Interactive map view with restaurant markers"""
    return render(request, "nomz/diner/map.html")


@login_required
def search_results(request):
    """Restaurant search results page"""
    query = request.GET.get("q", "")
    neighborhood = request.GET.get("neighborhood", "")

    return render(
        request,
        "nomz/diner/search_results.html",
        {"initial_query": query, "initial_neighborhood": neighborhood},
    )


@login_required
def restaurant_detail(request, restaurant_id):
    """Restaurant detail page with reviews"""
    return render(
        request, "nomz/diner/restaurant_detail.html", {"restaurant_id": restaurant_id}
    )


@login_required
def add_review(request, restaurant_id):
    """Add review form"""
    return render(
        request, "nomz/diner/add_review.html", {"restaurant_id": restaurant_id}
    )


def messages_view(request):
    """Messages/conversations list"""
    return render(request, "nomz/diner/messages.html")


@login_required
def message_thread(request, conversation_id):
    """Specific message thread"""
    return render(
        request, "nomz/diner/message_thread.html", {"conversation_id": conversation_id}
    )


@login_required
def start_message(request, restaurant_id):
    """Start new conversation with restaurant"""
    return render(
        request, "nomz/diner/message_thread.html", {"restaurant_id": restaurant_id}
    )


def user_profile(request):
    """User profile and preferences"""
    return render(request, "nomz/diner/profile.html")


@login_required
def recommendations(request):
    """Personalized restaurant recommendations"""
    return render(request, "nomz/diner/recommendations.html")


@login_required
def friends_chat(request):
    """Friends chat and social discovery"""
    return render(request, "nomz/diner/friends_chat.html")


@login_required
def report_content(request, content_type, content_id):
    """Report review or user"""
    return render(
        request,
        "nomz/diner/report_content.html",
        {"content_type": content_type, "content_id": content_id},
    )


# ==============================================================================
# RESTAURANT OWNER PAGES
# ==============================================================================


def restaurant_profile(request):
    """Restaurant owner dashboard/profile"""
    return render(request, "nomz/restaurant/profile.html")


@login_required
def photo_management(request):
    """Restaurant photo upload and management"""
    return render(request, "nomz/restaurant_photos.html")


@login_required
def claim_restaurant(request):
    """Claim existing restaurant listing"""
    from nomz.models import Restaurant

    has_restaurant = Restaurant.objects.filter(owner=request.user).exists()
    return render(
        request, "nomz/restaurant/claim.html", {"has_restaurant": has_restaurant}
    )


@login_required
def create_restaurant(request):
    """Create new restaurant listing"""
    return render(request, "nomz/restaurant/create.html")


@login_required
def edit_restaurant(request):
    """Edit restaurant information"""
    return render(request, "nomz/restaurant/edit.html")


@login_required
def manage_activation(request):
    """Toggle restaurant active/inactive status"""
    return render(request, "nomz/restaurant/activate.html")


@login_required
def restaurant_map(request):
    """Restaurant owner's map view"""
    return render(request, "nomz/diner/map.html", {"account_type": "restaurant"})


# ==============================================================================
# ADMIN PAGES
# ==============================================================================


@staff_member_required
def admin_dashboard(request):
    """Admin dashboard with stats and charts"""
    return render(request, "nomz/admin/dashboard.html")


@staff_member_required
def admin_map(request):
    """Admin map view"""
    return render(request, "nomz/diner/map.html", {"account_type": "admin"})


@staff_member_required
def admin_moderation(request):
    """Content moderation dashboard"""
    return render(request, "nomz/admin/moderation.html")


@staff_member_required
def resolve_report(request, report_id):
    """Resolve specific moderation report"""
    return render(request, "nomz/admin/moderation.html", {"report_id": report_id})


@staff_member_required
def pending_approvals(request):
    """Restaurant approval queue"""
    return render(request, "nomz/admin/pending_approvals.html")


@staff_member_required
def manage_users(request):
    """User management dashboard"""
    return render(request, "nomz/admin/users.html")


@staff_member_required
def admin_logs(request):
    """System audit logs"""
    return render(request, "nomz/admin/logs.html")


@staff_member_required
def approved_accounts(request):
    """View approved restaurant accounts"""
    return render(request, "nomz/admin/accounts.html", {"status": "approved"})


@staff_member_required
def rejected_accounts(request):
    """View rejected restaurant accounts"""
    return render(request, "nomz/admin/accounts.html", {"status": "rejected"})


# ==============================================================================
# LEGACY REDIRECTS
# ==============================================================================


def admin_login(request):
    """Redirect to signin with admin flag"""
    return redirect("/signin/?admin=true")


@login_required
def manage_preferences(request):
    """Legacy redirect to profile"""
    return redirect("/profile/")


@login_required
def manage_availability(request):
    """Availability management page."""
    return render(request, "nomz/restaurant/profile.html")


def manage_communication_settings(request):
    """Communication settings page."""
    return render(request, "nomz/restaurant/profile.html")


@login_required
def upload_photo(request):
    """Photo upload page."""
    return render(request, "nomz/restaurant_photos.html")
