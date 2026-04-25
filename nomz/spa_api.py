"""
JSON endpoints for the React SPA (session auth, photos, admin summaries).
Uses session cookies + @csrf_exempt on mutating POSTs (same pattern as api_views).
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import login, logout
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django_otp import user_has_device, match_token

from django.contrib.auth.decorators import login_required

from .forms import (
    AdminLoginForm,
    RestaurantActivationForm,
    RestaurantAvailabilityForm,
    RestaurantCommunicationSettingsForm,
    RestaurantPhotoForm,
    RestaurantProfileForm,
    UserPreferenceForm,
    UserRegisterForm,
    ReviewForm,
    ModerationReportForm,
)
from .models import (
    CompositeScoreAnomaly,
    FriendConversation,
    FriendMessage,
    FriendSharedRestaurant,
    LoginLog,
    ModerationReport,
    Restaurant,
    RestaurantOwnershipClaim,
    RestaurantPhoto,
    Review,
    ReviewResponse,
    SystemAuditLog,
    UserPreference,
    UserProfile,
)
from .scoring import refresh_restaurant_composite
from .restaurant_sorting import (
    normalize_sort_key,
    recommend_restaurants_for_user,
    sort_restaurant_queryset,
)

from .api_views import (  # reuse helpers
    _is_diner,
    _is_restaurant_owner,
    _json_error,
)


def _staff_json_required(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return _json_error("Staff access required.", status=403)
    return None


def session_payload(request) -> dict:
    if not request.user.is_authenticated:
        return {"authenticated": False}
    u = request.user
    role = None
    profile_data = None
    if hasattr(u, "userprofile"):
        role = u.userprofile.role
        profile_data = {
            "is_approved": u.userprofile.is_approved,
            "is_rejected": u.userprofile.is_rejected,
            "role": u.userprofile.role,
        }
    return {
        "authenticated": True,
        "user_id": u.id,
        "username": u.username,
        "email": u.email or "",
        "role": role,
        "is_staff": u.is_staff,
        "is_superuser": u.is_superuser,
        "userprofile": profile_data,
    }


@require_http_methods(["GET", "HEAD"])
def auth_session(request):
    return JsonResponse(session_payload(request))


@csrf_exempt
@require_http_methods(["POST"])
def auth_register(request):
    if request.user.is_authenticated:
        return JsonResponse(session_payload(request))

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    form = UserRegisterForm(
        {
            "email": body.get("email", ""),
            "username": body.get("username", ""),
            "role": body.get("role", ""),
            "password1": body.get("password1", ""),
            "password2": body.get("password2", ""),
        }
    )
    if form.is_valid():
        user = form.save()
        login(request, user)
        return JsonResponse(session_payload(request), status=201)

    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"success": False, "errors": errors}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def auth_login(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        return _json_error("Username and password are required.")

    form = AuthenticationForm(
        request,
        data={"username": username, "password": password},
    )
    if form.is_valid():
        user = form.get_user()
        # Check if user has a confirmed 2FA device
        if user_has_device(user, confirmed=True):
            request.session["_2fa_user_id"] = user.id
            return JsonResponse({"requires_2fa": True, "authenticated": False})
        login(request, user)
        # Force a success log entry if signal is flaky
        from .models import LoginLog
        from .signals import get_client_ip

        LoginLog.objects.get_or_create(
            user=user,
            username=user.username,
            timestamp__gte=timezone.now() - timedelta(seconds=5),
            defaults={
                "ip_address": get_client_ip(request),
                "status": "Success",
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            },
        )
        return JsonResponse(session_payload(request))

    err_msg = "Invalid username or password."
    if form.errors.get("__all__"):
        err_msg = "; ".join(str(e) for e in form.errors["__all__"])
    return _json_error(err_msg, status=401)


@csrf_exempt
@require_http_methods(["POST"])
def auth_admin_login(request):
    """
    Same rules as views.admin_login / AdminLoginForm: built-in `admin` credentials plus
    ADMIN_SECURITY_CODE (no generic staff login through this endpoint).
    """
    if request.user.is_authenticated and request.user.is_staff:
        return JsonResponse(session_payload(request))

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    security_code = (body.get("security_code") or "").strip()

    if not username or not password or not security_code:
        return _json_error("Username, password, and security code are required.")

    form = AdminLoginForm(
        request,
        data={
            "username": username,
            "password": password,
            "security_code": security_code,
        },
    )
    if form.is_valid():
        user = form.get_user()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return JsonResponse(session_payload(request))

    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    if "__all__" in errors and len(errors) == 1:
        return JsonResponse(
            {"error": errors["__all__"][0], "errors": errors},
            status=401,
        )
    return JsonResponse(
        {
            "error": "Invalid admin credentials or security code.",
            "errors": errors,
        },
        status=400,
    )


@csrf_exempt
@require_http_methods(["POST"])
def auth_2fa_verify(request):
    """Verify a 2FA token for a pending login."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    user_id = request.session.get("_2fa_user_id")
    if not user_id:
        return _json_error("No pending two-factor authentication.", status=400)

    token = (body.get("token") or "").strip()
    if not token:
        return _json_error("Authentication code is required.")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return _json_error("Invalid session.", status=400)

    device = match_token(user, token)
    if device is not None:
        del request.session["_2fa_user_id"]
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return JsonResponse(session_payload(request))

    return _json_error("Invalid authentication code.", status=401)


@csrf_exempt
@require_http_methods(["POST"])
def auth_logout(request):
    logout(request)
    return JsonResponse({"authenticated": False})


@csrf_exempt
@require_http_methods(["POST"])
def auth_password_reset_request(request):
    """Send a password-reset email (SPA flow)."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    email = (body.get("email") or "").strip()
    if not email:
        return _json_error("Email is required.")

    form = PasswordResetForm({"email": email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name="registration/password_reset_email_spa.html",
            subject_template_name="registration/password_reset_subject.txt",
        )
    # Always return success to prevent email enumeration
    return JsonResponse({"success": True})


@csrf_exempt
@require_http_methods(["POST"])
def auth_password_reset_confirm(request):
    """Validate uid/token and set a new password (SPA flow)."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    uid = body.get("uid", "")
    token = body.get("token", "")
    new_password1 = body.get("new_password1", "")
    new_password2 = body.get("new_password2", "")

    if not uid or not token:
        return _json_error("Invalid reset link.", status=400)
    if not new_password1 or not new_password2:
        return _json_error("Both password fields are required.", status=400)

    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return _json_error("Invalid reset link.", status=400)

    if not default_token_generator.check_token(user, token):
        return JsonResponse(
            {
                "success": False,
                "expired": True,
                "error": "Reset link has expired or is invalid.",
            },
            status=400,
        )

    form = SetPasswordForm(
        user, {"new_password1": new_password1, "new_password2": new_password2}
    )
    if form.is_valid():
        form.save()
        return JsonResponse({"success": True})

    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"success": False, "errors": errors}, status=400)


# --- Restaurant photos ---


@login_required(login_url="landing")
@require_GET
def restaurant_photos_data(request):

    if not _is_restaurant_owner(request.user):
        return _json_error("Restaurant owners only.", status=403)

    restaurant = Restaurant.objects.filter(owner=request.user).first()
    if not restaurant:
        return JsonResponse({"photos": []})

    photos = []
    for p in restaurant.photos.all():
        url = p.photo.url if p.photo else ""
        photos.append(
            {
                "id": p.id,
                "url": url,
                "caption": p.caption or "",
                "is_primary": p.is_primary,
            }
        )
    return JsonResponse({"restaurant_id": restaurant.id, "photos": photos})


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def restaurant_photo_upload(request):

    if not _is_restaurant_owner(request.user):
        return HttpResponseForbidden("Restaurant owners only.")

    restaurant = get_object_or_404(Restaurant, owner=request.user)
    form = RestaurantPhotoForm(request.POST, request.FILES)
    if form.is_valid():
        photo = form.save(commit=False)
        photo.restaurant = restaurant
        photo.save()
        url = photo.photo.url if photo.photo else ""
        return JsonResponse(
            {
                "id": photo.id,
                "url": url,
                "caption": photo.caption or "",
                "is_primary": photo.is_primary,
            },
            status=201,
        )
    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"errors": errors}, status=400)


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def restaurant_photo_delete(request, photo_id):

    if not _is_restaurant_owner(request.user):
        return HttpResponseForbidden("Restaurant owners only.")

    photo = get_object_or_404(RestaurantPhoto, id=photo_id)
    if photo.restaurant.owner_id != request.user.id:
        return HttpResponseForbidden("Permission denied.")

    photo.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def restaurant_photo_set_primary(request, photo_id):

    if not _is_restaurant_owner(request.user):
        return HttpResponseForbidden("Restaurant owners only.")

    photo = get_object_or_404(RestaurantPhoto, id=photo_id)
    if photo.restaurant.owner_id != request.user.id:
        return HttpResponseForbidden("Permission denied.")

    photo.is_primary = True
    photo.save()
    return JsonResponse({"ok": True})


# --- Profile activation ---


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["GET", "POST"])
def restaurant_activation_api(request):

    if not _is_restaurant_owner(request.user):
        return _json_error("Restaurant owners only.", status=403)

    restaurant = get_object_or_404(Restaurant, owner=request.user)

    if request.method == "GET":
        return JsonResponse({"is_active": restaurant.is_active})

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    if "is_active" not in body:
        return _json_error("is_active is required.")

    form = RestaurantActivationForm(
        {"is_active": bool(body["is_active"])}, instance=restaurant
    )
    if form.is_valid():
        form.save()
        return JsonResponse({"is_active": restaurant.is_active})
    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"errors": errors}, status=400)


# --- Diner preferences ---


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["GET", "POST"])
def diner_preferences_api(request):

    if not _is_diner(request.user):
        return _json_error("Diners only.", status=403)

    preferences, _ = UserPreference.objects.get_or_create(user=request.user)

    if request.method == "GET":
        return JsonResponse(
            {
                "favorite_cuisines": preferences.favorite_cuisines or [],
                "dietary_restrictions": preferences.dietary_restrictions or [],
                "price_preference": preferences.price_preference or "",
                "neighborhood_preference": preferences.neighborhood_preference or "",
            }
        )

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    form = UserPreferenceForm(body, instance=preferences)
    if form.is_valid():
        form.save()
        return JsonResponse({"success": True})

    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"errors": errors}, status=400)


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["GET", "POST", "PATCH"])
def diner_account_api(request):
    """Diner account fields for the SPA profile header (parity with Django user account data)."""
    if not _is_diner(request.user):
        return _json_error("Diners only.", status=403)

    u = request.user
    if request.method == "GET":
        review_count = Review.objects.filter(user=u, is_deleted=False).count()
        pref = getattr(u, "preferences", None)
        phone = getattr(pref, "phone_number", "") or ""
        return JsonResponse(
            {
                "username": u.username,
                "email": u.email or "",
                "first_name": u.first_name or "",
                "last_name": u.last_name or "",
                "phone_number": phone,
                "reviews_written": review_count,
            }
        )

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    # --- Username change (uniqueness enforced) ---
    new_username = (body.get("username") or "").strip()
    if new_username and new_username != u.username:
        if len(new_username) > 150:
            return _json_error("Username must be 150 characters or fewer.")
        import re

        if not re.match(r"^[\w.@+-]+$", new_username):
            return _json_error(
                "Username may only contain letters, digits, and @/./+/-/_."
            )
        from django.contrib.auth.models import User as AuthUser

        if (
            AuthUser.objects.filter(username__iexact=new_username)
            .exclude(pk=u.pk)
            .exists()
        ):
            return _json_error("That username is already taken.", status=409)
        u.username = new_username

    # --- Basic fields ---
    email = (body.get("email") or "").strip()
    if email:
        u.email = email
    u.first_name = (body.get("first_name") or "")[:150]
    u.last_name = (body.get("last_name") or "")[:150]
    u.save(update_fields=["username", "email", "first_name", "last_name"])

    # --- Phone number stored on UserPreference ---
    phone = (body.get("phone_number") or "").strip()[:30]
    try:
        pref, _ = UserPreference.objects.get_or_create(user=u)
        if hasattr(pref, "phone_number"):
            pref.phone_number = phone
            pref.save(update_fields=["phone_number"])
    except Exception:
        pass  # phone save is best-effort

    return JsonResponse({"success": True, "username": u.username})


# --- Admin JSON ---


@login_required(login_url="landing")
@require_GET
def admin_dashboard_summary(request):

    deny = _staff_json_required(request)
    if deny:
        return deny

    diner_count = UserProfile.objects.filter(role="diner").count()
    restaurant_count = Restaurant.objects.count()
    pending_approval_count = UserProfile.objects.filter(
        role="restaurant", is_approved=False, is_rejected=False
    ).count()
    approved_business_count = UserProfile.objects.filter(
        role="restaurant", is_approved=True
    ).count()
    rejected_business_count = UserProfile.objects.filter(
        role="restaurant", is_rejected=True
    ).count()
    pending_report_count = ModerationReport.objects.filter(status="PENDING").count()
    suspicious_count = LoginLog.objects.filter(is_suspicious=True).count()
    total_logs = LoginLog.objects.count()
    flagged_content = (
        Review.objects.filter(is_flagged=True).count()
        + Restaurant.objects.filter(is_flagged=True).count()
    )

    return JsonResponse(
        {
            "total_users": User.objects.count(),
            "total_restaurants": restaurant_count,
            "diner_count": diner_count,
            "pending_approvals": pending_approval_count,
            "approved_business_count": approved_business_count,
            "rejected_business_count": rejected_business_count,
            "pending_reports": pending_report_count,
            "suspicious_accounts": suspicious_count,
            "flagged_content": flagged_content,
            "total_logs": total_logs,
        }
    )


@require_GET
def admin_pending_approvals_data(request):

    deny = _staff_json_required(request)
    if deny:
        return deny

    pending_approvals = (
        User.objects.filter(userprofile__role="restaurant")
        .filter(
            Q(userprofile__is_approved=False, userprofile__is_rejected=False)
            | Q(restaurant_claims__status=RestaurantOwnershipClaim.STATUS_PENDING)
        )
        .distinct()
        .select_related("userprofile")
        .order_by("-date_joined")
    )
    pending_claims = (
        RestaurantOwnershipClaim.objects.filter(
            status=RestaurantOwnershipClaim.STATUS_PENDING
        )
        .select_related("restaurant", "claimant")
        .order_by("-created_at")
    )
    claims_by_user_id = {c.claimant_id: c for c in pending_claims}

    results = []
    for u in pending_approvals:
        claim = claims_by_user_id.get(u.id)
        res_name = "Unnamed Business"
        if claim and claim.restaurant:
            res_name = (
                claim.restaurant.display_name
                or claim.restaurant.name
                or "Unnamed Business"
            )

        results.append(
            {
                "id": u.id,
                "username": u.username,
                "email": u.email or "",
                "date_joined": u.date_joined.isoformat(),
                "restaurant_name": res_name,
                "business_email": (claim.business_email if claim else "") or "",
                "claim_details": (claim.proof_details if claim else "") or "",
                "has_pending_claim": claim is not None,
            }
        )

    return JsonResponse({"count": len(results), "results": results})


def _serialize_admin_restaurant_account_row(u: User) -> dict:
    # Try owner first, then fallback to most recent approved claim
    restaurant = Restaurant.objects.filter(owner=u).first()
    if not restaurant:
        claim = (
            RestaurantOwnershipClaim.objects.filter(
                claimant=u, status=RestaurantOwnershipClaim.STATUS_APPROVED
            )
            .select_related("restaurant")
            .first()
        )
        if claim:
            restaurant = claim.restaurant

    return {
        "id": u.id,
        "username": u.username,
        "email": u.email or "",
        "joined": u.date_joined.isoformat(),
        "name": restaurant.name if restaurant else "Unnamed Business",
    }


@login_required(login_url="landing")
@require_GET
def admin_approved_restaurant_accounts_data(request):
    """JSON list of approved restaurant-role accounts (parity with admin_approved_list.html)."""
    deny = _staff_json_required(request)
    if deny:
        return deny

    qs = (
        User.objects.filter(
            userprofile__role="restaurant", userprofile__is_approved=True
        )
        .select_related("userprofile")
        .order_by("-date_joined")
    )
    results = [_serialize_admin_restaurant_account_row(u) for u in qs]
    return JsonResponse({"count": len(results), "results": results})


@login_required(login_url="landing")
@require_GET
def admin_rejected_restaurant_accounts_data(request):
    """JSON list of rejected restaurant-role accounts (parity with admin_rejected_list.html)."""
    deny = _staff_json_required(request)
    if deny:
        return deny

    qs = (
        User.objects.filter(
            userprofile__role="restaurant", userprofile__is_rejected=True
        )
        .select_related("userprofile")
        .order_by("-date_joined")
    )
    results = [_serialize_admin_restaurant_account_row(u) for u in qs]
    return JsonResponse({"count": len(results), "results": results})


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def admin_approve_user_api(request, user_id):

    deny = _staff_json_required(request)
    if deny:
        return deny

    user_to_approve = get_object_or_404(User, id=user_id)
    pending_claim = (
        RestaurantOwnershipClaim.objects.filter(
            claimant=user_to_approve,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )
        .select_related("restaurant")
        .first()
    )

    notes = "Approved via SPA admin API."
    try:
        data = json.loads(request.body)
        if data.get("notes"):
            notes = data["notes"]
    except json.JSONDecodeError:
        pass

    if pending_claim:
        try:
            pending_claim.approve(
                reviewer=request.user,
                notes=notes,
            )
        except ValidationError as exc:
            return _json_error(str(exc), status=400)

    if hasattr(user_to_approve, "userprofile"):
        profile = user_to_approve.userprofile
        profile.is_approved = True
        profile.is_rejected = False
        profile.role = "restaurant"  # Ensure role is set on approval
        profile.save()

    return JsonResponse({"ok": True, "status": "approved"})


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def admin_reject_user_api(request, user_id):

    deny = _staff_json_required(request)
    if deny:
        return deny

    user_to_reject = get_object_or_404(User, id=user_id)

    pending_claims = RestaurantOwnershipClaim.objects.filter(
        claimant=user_to_reject,
        status=RestaurantOwnershipClaim.STATUS_PENDING,
    )
    notes = "Rejected via SPA admin API."
    try:
        data = json.loads(request.body)
        if data.get("notes"):
            notes = data["notes"]
    except json.JSONDecodeError:
        pass

    for claim in pending_claims:
        claim.reject(
            reviewer=request.user,
            notes=notes,
        )

    if hasattr(user_to_reject, "userprofile"):
        profile = user_to_reject.userprofile
        profile.is_approved = False
        profile.is_rejected = True
        profile.save()

    return JsonResponse({"ok": True})


@require_GET
def admin_moderation_data(request):

    deny = _staff_json_required(request)
    if deny:
        return deny

    pending = ModerationReport.objects.filter(status="PENDING").order_by("-created_at")
    resolved = ModerationReport.objects.exclude(status="PENDING").order_by(
        "-created_at"
    )[:25]

    def row(r: ModerationReport):
        return {
            "id": r.id,
            "reason": r.reason,
            "details": r.details,
            "status": r.status,
            "reporter_username": r.reporter.username,
            "created_at": r.created_at.isoformat(),
            "review_id": r.review_id,
            "reported_user_id": r.reported_user_id,
        }

    return JsonResponse(
        {
            "pending": [row(r) for r in pending],
            "resolved": [row(r) for r in resolved],
        }
    )


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def admin_resolve_report_api(request, report_id):

    deny = _staff_json_required(request)
    if deny:
        return deny

    report = get_object_or_404(ModerationReport, id=report_id)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    action = (body.get("action") or "").strip()
    moderator_note = (body.get("moderator_note") or "").strip()

    if action == "dismiss":
        report.status = "DISMISSED"
        report.action_taken = "No action taken"
    elif action == "flag_fraud":
        if report.review:
            report.review.is_flagged = True
            report.review.save()
            report.action_taken = "Review flagged as fraudulent"
        elif report.reported_user:
            if hasattr(report.reported_user, "userprofile"):
                report.reported_user.userprofile.is_flagged = True
                report.reported_user.userprofile.save()
            Restaurant.objects.filter(owner=report.reported_user).update(
                is_flagged=True
            )
            report.action_taken = "User and associated restaurant(s) flagged for fraud"
        report.status = "RESOLVED"
    elif action == "unflag":
        if report.review:
            report.review.is_flagged = False
            report.review.save()
            report.action_taken = "Review un-flagged"
        elif report.reported_user:
            if hasattr(report.reported_user, "userprofile"):
                report.reported_user.userprofile.is_flagged = False
                report.reported_user.userprofile.save()
            Restaurant.objects.filter(owner=report.reported_user).update(
                is_flagged=False
            )
            report.action_taken = "User and associated restaurant(s) un-flagged"
        report.status = "PENDING"
    elif action == "delete":
        if report.review:
            report.review.is_deleted = True
            report.review.save()
            report.action_taken = "Review soft-deleted"
        report.status = "RESOLVED"
    elif action == "reevaluate":
        report.status = "PENDING"
        report.action_taken = "Moved back to pending for re-evaluation"
    else:
        return _json_error("Invalid action.", status=400)

    report.moderator_note = moderator_note
    report.resolved_at = timezone.now()
    report.save()

    SystemAuditLog.objects.create(
        actor_user=request.user,
        actor_username=request.user.username,
        level="WARNING" if action not in ("dismiss", "reevaluate") else "INFO",
        action=f"moderation_{action}",
        request_path=request.path,
        http_method=request.method,
        ip_address=request.META.get("REMOTE_ADDR"),
        metadata={
            "report_id": report.id,
            "action": action,
            "target": str(report),
        },
    )
    return JsonResponse({"ok": True})


@require_GET
def admin_users_data(request):

    deny = _staff_json_required(request)
    if deny:
        return deny

    users = (
        User.objects.all()
        .exclude(pk=request.user.pk)
        .select_related("userprofile")
        .order_by("-date_joined")
    )
    from django.db.models import Exists, OuterRef, Subquery, F, Value
    from django.db.models.functions import Coalesce
    from django.utils import timezone

    latest_log = LoginLog.objects.filter(username=OuterRef("username")).order_by(
        "-timestamp"
    )
    users = (
        users.annotate(
            has_suspicious_activity=Exists(latest_log.filter(is_user_suspicious=True)),
            last_login_at=Subquery(latest_log.values("timestamp")[:1]),
            last_ip=Subquery(latest_log.values("ip_address")[:1]),
        )
        .annotate(
            sort_date=Coalesce(
                F("last_login_at"),
                Value(timezone.make_aware(timezone.datetime(2000, 1, 1))),
            )
        )
        .order_by("-sort_date", "-date_joined")
    )

    payload = []
    for u in users:
        payload.append(
            {
                "id": u.id,
                "username": u.username,
                "email": u.email or "",
                "account_type": (
                    getattr(u.userprofile, "role", "diner")
                    if hasattr(u, "userprofile")
                    else "diner"
                ),
                "is_active": u.is_active,
                "date_joined": u.date_joined.isoformat(),
                "last_login": u.last_login_at.isoformat() if u.last_login_at else None,
                "last_ip": u.last_ip or "N/A",
                "review_count": getattr(u, "review_count", 0),
                "report_count": getattr(u, "report_count", 0),
                "has_suspicious_activity": getattr(u, "has_suspicious_activity", False),
                "is_flagged": (
                    getattr(u.userprofile, "is_flagged", False)
                    if hasattr(u, "userprofile")
                    else False
                ),
            }
        )
    return JsonResponse({"count": len(payload), "results": payload})


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def admin_toggle_user_active_api(request, user_id):

    deny = _staff_json_required(request)
    if deny:
        return deny

    user_to_toggle = get_object_or_404(User, id=user_id)
    if user_to_toggle.is_superuser:
        return _json_error("Cannot toggle superuser.", status=400)
    if user_to_toggle == request.user:
        return _json_error("Cannot toggle yourself.", status=400)

    user_to_toggle.is_active = not user_to_toggle.is_active
    user_to_toggle.save()
    return JsonResponse({"ok": True, "is_active": user_to_toggle.is_active})


@require_GET
def admin_login_logs_data(request):

    deny = _staff_json_required(request)
    if deny:
        return deny

    logs = LoginLog.objects.all().order_by("-timestamp")[:200]
    payload = [
        {
            "id": log.id,
            "username": log.username,
            "status": log.status,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": log.ip_address or "",
            "is_suspicious": log.is_suspicious,
            "is_user_suspicious": log.is_user_suspicious,
        }
        for log in logs
    ]
    return JsonResponse({"count": len(payload), "results": payload})


# ── Restaurant detail, reviews, reports (SPA) ──────────────────────


@require_GET
def restaurant_detail_data(request, restaurant_id):
    """Return JSON detail for a single restaurant + its reviews."""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    is_owner_flagged = False
    owner_id = None
    messaging_enabled = restaurant.messaging_enabled
    if restaurant.owner:
        owner_id = restaurant.owner.id
        if hasattr(restaurant.owner, "userprofile"):
            is_owner_flagged = getattr(
                restaurant.owner.userprofile, "is_flagged", False
            )

    reviews_qs = (
        restaurant.reviews.filter(is_deleted=False)
        .select_related("user", "restaurant_response", "restaurant_response__responder")
        .order_by("-created_at")
    )
    reviews_list = []
    for r in reviews_qs:
        review_data = {
            "id": r.id,
            "username": r.user.username,
            "rating": r.rating,
            "food_quality_rating": r.food_quality_rating,
            "service_quality_rating": r.service_quality_rating,
            "value_rating": r.value_rating,
            "dietary_accommodation_rating": r.dietary_accommodation_rating,
            "cleanliness_rating": r.cleanliness_rating,
            "comment": r.comment or "",
            "created_at": r.created_at.isoformat(),
            "is_flagged": r.is_flagged,
        }
        try:
            resp = r.restaurant_response
            review_data["owner_response"] = {
                "response_text": resp.response_text,
                "responder_username": resp.responder.username,
                "created_at": resp.created_at.isoformat(),
                "updated_at": resp.updated_at.isoformat(),
            }
        except ReviewResponse.DoesNotExist:
            review_data["owner_response"] = None
        reviews_list.append(review_data)

    data = {
        "id": restaurant.id,
        "name": restaurant.display_name or restaurant.name,
        "cuisine": restaurant.cuisine or "",
        "cuisine_tags": restaurant.cuisine_tags or [],
        "neighborhood": restaurant.neighborhood or "",
        "address": ", ".join(
            p
            for p in [
                restaurant.building or "",
                restaurant.street or "",
                restaurant.borough or "",
                restaurant.zip_code or "",
            ]
            if p
        ),
        "description": restaurant.description or "",
        "phone": restaurant.phone or "",
        "price_range": restaurant.price_range or "",
        "hours_open": (
            restaurant.hours_open.strftime("%H:%M") if restaurant.hours_open else ""
        ),
        "hours_close": (
            restaurant.hours_close.strftime("%H:%M") if restaurant.hours_close else ""
        ),
        "is_flagged": restaurant.is_flagged,
        "is_owner_flagged": is_owner_flagged,
        "owner_id": owner_id,
        "owner_username": restaurant.owner.username if restaurant.owner else None,
        "messaging_enabled": messaging_enabled,
        "composite_score": (
            float(restaurant.composite_score)
            if restaurant.composite_score is not None
            else None
        ),
        "grade": restaurant.grade_latest or "",
        "reviews": reviews_list,
    }
    return JsonResponse(data)


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def restaurant_add_review(request, restaurant_id):
    """Submit a review for a restaurant (JSON)."""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    form = ReviewForm(body)
    if form.is_valid():
        review = form.save(commit=False)
        review.restaurant = restaurant
        review.user = request.user
        review.save()
        return JsonResponse(
            {
                "success": True,
                "review_id": review.id,
            },
            status=201,
        )

    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"success": False, "errors": errors}, status=400)


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def report_content_api(request):
    """Report a review or user (JSON)."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    content_type = body.get("content_type", "")
    content_id = body.get("content_id")

    if content_type not in ("review", "user") or not content_id:
        return _json_error("Invalid report target.", status=400)

    review = None
    reported_user = None

    if content_type == "review":
        try:
            review = Review.objects.get(id=content_id)
        except Review.DoesNotExist:
            return _json_error("Review not found.", status=404)
    else:
        from django.contrib.auth.models import User as AuthUser

        try:
            reported_user = AuthUser.objects.get(id=content_id)
        except AuthUser.DoesNotExist:
            return _json_error("User not found.", status=404)

    form = ModerationReportForm(
        {"reason": body.get("reason", ""), "details": body.get("details", "")}
    )
    if form.is_valid():
        report = form.save(commit=False)
        report.reporter = request.user
        report.review = review
        report.reported_user = reported_user
        report.save()
        return JsonResponse({"success": True, "report_id": report.id}, status=201)

    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"success": False, "errors": errors}, status=400)


# --- Restaurant profile, availability, communication (parity with Django HTML forms) ---


def _time_for_input(t) -> str:
    if not t:
        return ""
    return t.strftime("%H:%M")


def _response_hours_display(t) -> str:
    if not t:
        return ""
    return t.strftime("%H:%M")


def _unavailable_until_for_input(dt) -> str:
    if not dt:
        return ""
    local = timezone.localtime(dt)
    return local.strftime("%Y-%m-%dT%H:%M")


def _parse_unavailable_until(raw) -> str | None:
    """Return a string suitable for DateTimeField / form parsing, or None to clear."""
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    if not s:
        return None
    if "T" not in s and " " in s:
        s = s.replace(" ", "T", 1)
    dt = parse_datetime(s)
    if dt is None:
        return s
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M:%S")


def _cuisine_and_price_choices():
    return {
        "cuisine_choices": [
            {"value": v, "label": lbl} for v, lbl in Restaurant.CUISINE_CHOICES
        ],
        "price_choices": [
            {"value": v, "label": lbl} for v, lbl in Restaurant.PRICE_CHOICES
        ],
    }


def _owner_visibility_rank(restaurant: Restaurant) -> tuple[int | None, int]:
    """Rank among active, visible restaurants by composite_score (1 = highest score)."""
    base = Restaurant.objects.filter(
        Q(owner__userprofile__is_approved=True) | Q(owner__isnull=True),
        is_active=True,
    )
    total = base.count()
    if restaurant.composite_score is None:
        return None, total
    higher = (
        base.exclude(pk=restaurant.pk)
        .filter(composite_score__gt=restaurant.composite_score)
        .count()
    )
    return higher + 1, total


def _serialize_owner_restaurant(restaurant: Restaurant) -> dict:
    rank, total_visible = _owner_visibility_rank(restaurant)
    review_count = restaurant.reviews.filter(is_deleted=False).count()
    # Derive messaging hours display
    rhs = _response_hours_display(restaurant.response_hours_start)
    rhe = _response_hours_display(restaurant.response_hours_end)
    if rhs and rhe:
        messaging_hours_label = f"{rhs} – {rhe}"
    elif rhs:
        messaging_hours_label = f"From {rhs}"
    elif rhe:
        messaging_hours_label = f"Until {rhe}"
    else:
        messaging_hours_label = "Not set (always available)"

    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "username": restaurant.owner.username if restaurant.owner else "",
        "description": restaurant.description or "",
        "cuisine_type": restaurant.cuisine_type,
        "price_range": restaurant.price_range,
        "hours_open": _time_for_input(restaurant.hours_open),
        "hours_close": _time_for_input(restaurant.hours_close),
        "address": restaurant.address or "",
        "phone": restaurant.phone or "",
        "website": restaurant.website or "",
        "email": restaurant.email or "",
        "is_active": restaurant.is_active,
        "messaging_enabled": restaurant.messaging_enabled,
        "messaging_hours_display": messaging_hours_label,
        "response_hours_start": _response_hours_display(
            restaurant.response_hours_start
        ),
        "response_hours_end": _response_hours_display(restaurant.response_hours_end),
        "is_temporarily_unavailable": restaurant.is_temporarily_unavailable,
        "unavailable_reason": restaurant.unavailable_reason or "",
        "unavailable_until": _unavailable_until_for_input(restaurant.unavailable_until),
        "created_at": (
            restaurant.created_at.strftime("%B %d, %Y")
            if hasattr(restaurant, "created_at") and restaurant.created_at
            else "Recently"
        ),
        "owner_joined": (
            restaurant.owner.date_joined.strftime("%B %d, %Y")
            if restaurant.owner
            else "Recently"
        ),
        "is_approved": (
            restaurant.owner.userprofile.is_approved
            if restaurant.owner and hasattr(restaurant.owner, "userprofile")
            else False
        ),
        "is_rejected": (
            restaurant.owner.userprofile.is_rejected
            if restaurant.owner and hasattr(restaurant.owner, "userprofile")
            else False
        ),
        "composite_score": (
            float(restaurant.composite_score)
            if restaurant.composite_score is not None
            else None
        ),
        "inspection_rating": (
            float(restaurant.grade_score_latest)
            if restaurant.grade_score_latest is not None
            else None
        ),
        "review_count": review_count,
        "citywide_rank": rank,
        "citywide_total": total_visible,
        "completion_count": sum(
            1
            for f in [
                restaurant.name,
                restaurant.description,
                restaurant.cuisine_type,
                restaurant.price_range,
                restaurant.hours_open,
                restaurant.hours_close,
                restaurant.address,
                restaurant.phone,
                restaurant.website,
                restaurant.email,
            ]
            if f
        ),
        "completion_total": 10,
    }


def _search_results_payload(request):
    query = request.GET.get("q", "").strip()
    neighborhood = request.GET.get("neighborhood", "").strip()
    sort_by = normalize_sort_key(request.GET.get("sort_by", "composite_desc"))

    base_restaurants = Restaurant.objects.filter(
        Q(owner__userprofile__is_approved=True) | Q(owner__isnull=True), is_active=True
    ).select_related("owner")
    if query:
        base_restaurants = base_restaurants.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(cuisine__icontains=query)
            | Q(cuisine_type__icontains=query)
            | Q(cuisine_tags__icontains=query)
        )
    if neighborhood:
        base_restaurants = base_restaurants.filter(
            Q(neighborhood__iexact=neighborhood) | Q(borough__iexact=neighborhood)
        )

    base_restaurants = sort_restaurant_queryset(base_restaurants, sort_by)

    results = []
    for restaurant in base_restaurants:
        fallback_cuisine = restaurant.cuisine or restaurant.cuisine_type or ""
        if not fallback_cuisine and restaurant.cuisine_tags:
            fallback_cuisine = ", ".join(
                str(tag) for tag in restaurant.cuisine_tags[:3]
            )
        results.append(
            {
                "id": restaurant.id,
                "name": restaurant.name,
                "description": restaurant.description or "",
                "cuisine": fallback_cuisine,
                "neighborhood": restaurant.neighborhood or restaurant.borough or "",
                "composite_score": restaurant.composite_score,
                "price_label": restaurant.get_price_range_display(),
                "rating_score": restaurant.grade_score_latest,
                "is_flagged": restaurant.is_flagged,
                "has_owner": restaurant.owner_id is not None,
                "messaging_enabled": restaurant.messaging_enabled,
            }
        )

    all_neighborhoods = sorted(
        {
            r.neighborhood or r.borough
            for r in Restaurant.objects.filter(
                Q(owner__userprofile__is_approved=True) | Q(owner__isnull=True),
                is_active=True,
            )
            if (r.neighborhood or r.borough)
        }
    )

    return {
        "results": results,
        "query": query,
        "neighborhood": neighborhood,
        "sort_by": sort_by,
        "all_neighborhoods": all_neighborhoods,
    }


def _recommendation_card(restaurant: Restaurant) -> dict:
    fallback_cuisine = restaurant.cuisine or restaurant.cuisine_type or ""
    if not fallback_cuisine and restaurant.cuisine_tags:
        fallback_cuisine = ", ".join(str(tag) for tag in restaurant.cuisine_tags[:3])
    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "description": (restaurant.description or "")[:280],
        "cuisine": fallback_cuisine,
        "neighborhood": restaurant.neighborhood or restaurant.borough or "",
        "composite_score": restaurant.composite_score,
        "price_label": restaurant.get_price_range_display(),
        "rating_score": restaurant.grade_score_latest,
        "is_flagged": restaurant.is_flagged,
    }


@login_required(login_url="landing")
@require_GET
def restaurant_search_api(request):
    """JSON equivalent of `restaurant_search` /search/ (Issue: SPA search results)."""
    return JsonResponse(_search_results_payload(request))


@login_required(login_url="landing")
@require_GET
def diner_recommendations_api(request):
    """Personalized recommendations featuring friend-shared restaurants and system picks."""
    if not _is_diner(request.user):
        return _json_error("Diners only.", status=403)

    # 1. Collect friend recommendations from chats
    friend_recs = Restaurant.objects.filter(
        id__in=FriendMessage.objects.filter(
            conversation__participants=request.user,
            restaurant_recommendation__isnull=False,
        )
        .exclude(sender=request.user)
        .values_list("restaurant_recommendation_id", flat=True)
    ).distinct()

    # 2. Check for system preferences
    has_prefs = False
    try:
        prefs = request.user.preferences
        if prefs.favorite_cuisines:
            has_prefs = True
    except UserPreference.DoesNotExist:
        pass

    # 3. Get system recommendations if preferences exist
    system_recs = []
    if has_prefs:
        system_recs = recommend_restaurants_for_user(request.user, limit=20)

    # Combine results (Friends first, then system)
    combined = list(friend_recs)
    system_ids = [r.id for r in combined]
    for sr in system_recs:
        if sr.id not in system_ids:
            combined.append(sr)

    # Message logic
    message = ""
    if not combined:
        if not has_prefs:
            message = "Add friends or set your preferences in your profile to see recommendations here!"
        else:
            message = "No restaurants currently match your saved preferences. Try updating your preferences."
    elif friend_recs.exists():
        message = "Restaurants recommended by your friends!"

    return JsonResponse(
        {
            "requires_preferences": not has_prefs and not friend_recs.exists(),
            "message": message,
            "restaurants": [
                {
                    "id": r.id,
                    "name": r.name,
                    "cuisine": r.cuisine_type,
                    "price_label": r.price_range,
                    "neighborhood": r.neighborhood,
                }
                for r in combined
            ],
        }
    )


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["GET", "POST"])
def restaurant_profile_api(request):
    """Create or edit restaurant profile (parity with restaurant/create/ and restaurant/edit/)."""
    if not _is_restaurant_owner(request.user):
        return _json_error("Restaurant owners only.", status=403)

    base_choices = _cuisine_and_price_choices()
    existing = Restaurant.objects.filter(owner=request.user).first()

    if request.method == "GET":
        profile = getattr(request.user, "userprofile", None)
        account_status = {
            "is_approved": getattr(profile, "is_approved", False),
            "is_rejected": getattr(profile, "is_rejected", False),
            "date_joined": request.user.date_joined.isoformat(),
        }
        if not existing:
            # User wants empty restaurants to still display the dashboard shell natively
            return JsonResponse(
                {
                    "has_restaurant": True,
                    **base_choices,
                    "restaurant": {
                        "name": "",
                        "username": request.user.username,
                        "email": request.user.email,
                        "phone": "",
                        "address": "",
                        "cuisine_type": "",
                        "price_range": "",
                        "hours_open": "",
                        "hours_close": "",
                        "messaging_hours_display": "",
                        "composite_score": None,
                        "inspection_rating": None,
                    },
                    "account_status": account_status,
                }
            )
        return JsonResponse(
            {
                "has_restaurant": True,
                **base_choices,
                "restaurant": _serialize_owner_restaurant(existing),
                "account_status": account_status,
            }
        )

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    if existing:
        form = RestaurantProfileForm(body, instance=existing)
        if form.is_valid():
            major_fields = {
                "name",
                "description",
                "cuisine_type",
                "price_range",
                "address",
            }
            changed = set(form.changed_data)

            profile = request.user.userprofile
            if changed.intersection(major_fields):
                profile.is_approved = False
                profile.is_rejected = False
                profile.save()

            form.save()
            return JsonResponse(
                {"success": True, "restaurant": _serialize_owner_restaurant(existing)}
            )
    else:
        form = RestaurantProfileForm(body)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.owner = request.user
            restaurant.save()
            return JsonResponse(
                {
                    "success": True,
                    "restaurant": _serialize_owner_restaurant(restaurant),
                },
                status=201,
            )

    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"success": False, "errors": errors}, status=400)


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["GET", "POST"])
def restaurant_availability_api(request):
    if not _is_restaurant_owner(request.user):
        return _json_error("Restaurant owners only.", status=403)

    restaurant = get_object_or_404(Restaurant, owner=request.user)

    if request.method == "GET":
        return JsonResponse(
            {
                "is_temporarily_unavailable": restaurant.is_temporarily_unavailable,
                "unavailable_reason": restaurant.unavailable_reason or "",
                "unavailable_until": _unavailable_until_for_input(
                    restaurant.unavailable_until
                ),
            }
        )

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    until_parsed = _parse_unavailable_until(body.get("unavailable_until"))
    data = {
        "is_temporarily_unavailable": bool(body.get("is_temporarily_unavailable")),
        "unavailable_reason": body.get("unavailable_reason") or "",
        "unavailable_until": until_parsed if until_parsed is not None else "",
    }
    form = RestaurantAvailabilityForm(data, instance=restaurant)
    if form.is_valid():
        form.save()
        return JsonResponse(
            {
                "success": True,
                "is_temporarily_unavailable": restaurant.is_temporarily_unavailable,
                "unavailable_reason": restaurant.unavailable_reason or "",
                "unavailable_until": _unavailable_until_for_input(
                    restaurant.unavailable_until
                ),
            }
        )
    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    return JsonResponse({"success": False, "errors": errors}, status=400)


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["GET", "POST"])
def restaurant_communication_api(request):
    if not _is_restaurant_owner(request.user):
        return _json_error("Restaurant owners only.", status=403)

    restaurant = get_object_or_404(Restaurant, owner=request.user)

    if request.method == "GET":
        return JsonResponse(
            {
                "messaging_enabled": restaurant.messaging_enabled,
                "response_hours_start": (
                    restaurant.response_hours_start.isoformat()
                    if restaurant.response_hours_start
                    else ""
                ),
                "response_hours_end": (
                    restaurant.response_hours_end.isoformat()
                    if restaurant.response_hours_end
                    else ""
                ),
            }
        )

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    data = {
        "messaging_enabled": bool(body.get("messaging_enabled", False)),
        "response_hours_start": body.get("response_hours_start") or "",
        "response_hours_end": body.get("response_hours_end") or "",
    }
    form = RestaurantCommunicationSettingsForm(data, instance=restaurant)
    if form.is_valid():
        form.save()
        return JsonResponse(
            {
                "success": True,
                "messaging_enabled": restaurant.messaging_enabled,
                "response_hours_start": _response_hours_display(
                    restaurant.response_hours_start
                ),
                "response_hours_end": _response_hours_display(
                    restaurant.response_hours_end
                ),
            }
        )
    errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
    if "__all__" in form.errors:
        errors["__all__"] = [str(e) for e in form.errors["__all__"]]
    return JsonResponse({"success": False, "errors": errors}, status=400)


# ---------------------------------------------------------------------------
#  Restaurant performance metrics
# ---------------------------------------------------------------------------


@login_required(login_url="landing")
@require_GET
def restaurant_performance_api(request):
    """Return composite score breakdown, history and review params for the restaurant owner."""
    if not _is_restaurant_owner(request.user):
        return _json_error("Restaurant owners only.", status=403)

    restaurant = Restaurant.objects.filter(owner=request.user).first()
    if not restaurant:
        # Fallback to an empty shell so empty accounts see dashes but retain the layout structure
        return JsonResponse(
            {
                "has_restaurant": True,
                "composite_score": None,
                "inspection_rating": None,
                "review_count": 0,
                "citywide_rank": None,
                "citywide_total": None,
                "approx_percentile": None,
                "breakdown": [
                    {
                        "label": "User Experience Signal",
                        "weight": 20,
                        "score": None,
                        "description": "0 review(s) on Nomz (detail breakdown is maintained server-side for the composite score).",
                    },
                    {
                        "label": "Inspection & Hygiene",
                        "weight": 20,
                        "score": None,
                        "description": "Grade N/A | Critical 0 | Non-critical 0 | Weighted contribution: —",
                    },
                    {
                        "label": "Price-to-Value Fit",
                        "weight": 20,
                        "score": None,
                        "description": "Derived from value ratings against expected value for price tier. | Weighted contribution: —",
                    },
                    {
                        "label": "Operational Reliability",
                        "weight": 40,
                        "score": None,
                        "description": "Based on profile status, temporary availability, and metadata quality. | Weighted contribution: —",
                    },
                ],
                "history": [],
                "review_params": {},
            }
        )

    from nomz.models import CompositeScoreHistory
    from django.db.models import Avg

    latest_history = (
        CompositeScoreHistory.objects.filter(restaurant=restaurant)
        .order_by("-calculated_at")
        .first()
    )

    rc = float(latest_history.review_component_score or 0) if latest_history else None
    ic = (
        float(latest_history.inspection_component_score or 0)
        if latest_history
        else None
    )
    pv = float(latest_history.price_value_score or 0) if latest_history else None
    op = float(latest_history.operational_score or 0) if latest_history else None
    review_count = (
        latest_history.review_count
        if latest_history and latest_history.review_count
        else 0
    )
    grade = restaurant.grade_latest or "N/A"

    breakdown = [
        {
            "label": "User Experience Signal",
            "weight": 20,
            "score": round(rc, 1) if rc is not None else None,
            "description": (
                f"{review_count} review(s) on Nomz (detail breakdown is maintained"
                " server-side for the composite score)."
            ),
        },
        {
            "label": "Inspection & Hygiene",
            "weight": 20,
            "score": round(ic, 1) if ic is not None else None,
            "description": (
                f"Grade {grade} | Critical 0 | Non-critical 0"
                f" | Weighted contribution: {round(ic * 0.20, 2) if ic is not None else '—'}"
            ),
        },
        {
            "label": "Price-to-Value Fit",
            "weight": 20,
            "score": round(pv, 1) if pv is not None else None,
            "description": (
                "Derived from value ratings against expected value for price tier."
                f" | Weighted contribution: {round(pv * 0.20, 2) if pv is not None else '—'}"
            ),
        },
        {
            "label": "Operational Reliability",
            "weight": 40,
            "score": round(op, 1) if op is not None else None,
            "description": (
                "Based on profile status, temporary availability, and metadata quality."
                f" | Weighted contribution: {round(op * 0.40, 2) if op is not None else '—'}"
            ),
        },
    ]

    history_qs = (
        CompositeScoreHistory.objects.filter(restaurant=restaurant)
        .order_by("calculated_at")
        .values("calculated_at", "composite_score")[:10]
    )
    history_data = [
        {
            "date": (
                h["calculated_at"].strftime("%b %d, %Y")
                if h.get("calculated_at")
                else ""
            ),
            "score": (
                round(float(h["composite_score"]), 1)
                if h.get("composite_score") is not None
                else None
            ),
        }
        for h in history_qs
    ]

    rank, total = _owner_visibility_rank(restaurant)
    approx_percentile = None
    if rank and total and total > 0:
        approx_percentile = round(((total - rank) / total) * 100)

    reviews = restaurant.reviews.filter(is_deleted=False)
    review_count_real = reviews.count()
    review_params = None
    if review_count_real > 0:
        agg = reviews.aggregate(
            food=Avg("food_quality_rating"),
            service=Avg("service_quality_rating"),
            ambience=Avg("ambience_rating"),
            location=Avg("location_rating"),
            value=Avg("value_rating"),
            cleanliness=Avg("cleanliness_rating"),
        )
        review_params = {
            k: round(float(v or 0), 1) for k, v in agg.items() if v is not None
        }

    return JsonResponse(
        {
            "has_restaurant": True,
            "composite_score": (
                float(restaurant.composite_score)
                if restaurant.composite_score is not None
                else None
            ),
            "inspection_rating": (
                float(restaurant.grade_score_latest)
                if restaurant.grade_score_latest is not None
                else None
            ),
            "review_count": review_count_real,
            "citywide_rank": rank,
            "citywide_total": total,
            "approx_percentile": approx_percentile,
            "breakdown": breakdown,
            "history": history_data,
            "review_params": review_params,
        }
    )


# ---------------------------------------------------------------------------
#  Review responses (restaurant owner)
# ---------------------------------------------------------------------------


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def review_respond_api(request, review_id):
    """Create or update a restaurant owner's public response to a review."""
    review = get_object_or_404(
        Review.objects.select_related("restaurant", "restaurant__owner"),
        id=review_id,
    )
    restaurant = review.restaurant

    if restaurant.owner_id != request.user.id:
        return _json_error("Only the owner of this restaurant can respond.", status=403)

    if review.is_deleted:
        return _json_error("Cannot respond to a deleted review.", status=400)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    response_text = (body.get("response_text") or "").strip()
    if not response_text:
        return _json_error("Response text is required.", status=400)

    review_response, created = ReviewResponse.objects.get_or_create(
        review=review,
        defaults={
            "restaurant": restaurant,
            "responder": request.user,
            "response_text": response_text,
        },
    )
    if not created:
        review_response.response_text = response_text
        review_response.responder = request.user
        review_response.save(update_fields=["response_text", "responder", "updated_at"])

    return JsonResponse(
        {
            "success": True,
            "created": created,
            "owner_response": {
                "response_text": review_response.response_text,
                "responder_username": review_response.responder.username,
                "created_at": review_response.created_at.isoformat(),
                "updated_at": review_response.updated_at.isoformat(),
            },
        }
    )


# ---------------------------------------------------------------------------
#  Admin: composite-score recalculation
# ---------------------------------------------------------------------------


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def admin_recalculate_scores_api(request):
    """Recalculate composite scores for one or all restaurants (JSON)."""
    err = _staff_json_required(request)
    if err:
        return err

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON.")

    restaurant_id = body.get("restaurant_id") or ""
    restaurant_name = (body.get("restaurant_name") or "").strip()

    queryset = Restaurant.objects.all().order_by("id")
    if restaurant_id:
        try:
            queryset = queryset.filter(id=int(restaurant_id))
        except (ValueError, TypeError):
            return _json_error("Restaurant ID must be a number.", status=400)
    elif restaurant_name:
        exact = queryset.filter(name__iexact=restaurant_name)
        if exact.count() == 1:
            queryset = exact
        elif exact.count() > 1:
            return _json_error("Multiple restaurants share that name.", status=400)
        else:
            partial = queryset.filter(name__icontains=restaurant_name)
            if partial.count() == 1:
                queryset = partial
            elif partial.count() > 1:
                return _json_error("Multiple restaurants match that name.", status=400)
            else:
                return _json_error("No restaurant found with that name.", status=404)

    total = queryset.count()
    if total == 0:
        return JsonResponse(
            {"success": True, "updated": 0, "anomaly_count": 0, "total": 0}
        )

    updated = 0
    anomaly_count = 0
    for restaurant in queryset.iterator():
        score_data = refresh_restaurant_composite(
            restaurant,
            trigger_source="admin_dashboard",
            triggered_by=request.user,
            trigger_note="Admin SPA dashboard trigger",
        )
        updated += 1
        anomaly_count += int(score_data.get("anomaly_count") or 0)

    SystemAuditLog.objects.create(
        actor_user=request.user,
        actor_username=request.user.username,
        level="INFO",
        action="admin_composite_score_recalculation",
        request_path=request.path,
        http_method=request.method,
        ip_address=request.META.get("REMOTE_ADDR"),
        metadata={
            "restaurant_id_filter": restaurant_id or None,
            "restaurant_name_filter": restaurant_name or None,
            "restaurants_updated": updated,
            "anomaly_flags_detected": anomaly_count,
        },
    )

    return JsonResponse(
        {
            "success": True,
            "updated": updated,
            "total": total,
            "anomaly_count": anomaly_count,
        }
    )


# ---------------------------------------------------------------------------
#  Admin: score anomalies
# ---------------------------------------------------------------------------


@login_required(login_url="landing")
@require_GET
def admin_score_anomalies_api(request):
    """Return list of score anomalies (pending and resolved)."""
    err = _staff_json_required(request)
    if err:
        return err

    anomalies = CompositeScoreAnomaly.objects.select_related(
        "restaurant", "resolved_by"
    ).order_by("-created_at")[:200]
    items = []
    for a in anomalies:
        items.append(
            {
                "id": a.id,
                "restaurant_id": a.restaurant_id,
                "restaurant_name": a.restaurant.display_name or a.restaurant.name,
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "details": a.details or {},
                "created_at": a.created_at.isoformat(),
                "is_resolved": a.is_resolved,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                "resolved_by": a.resolved_by.username if a.resolved_by else None,
            }
        )
    return JsonResponse({"anomalies": items})


@csrf_exempt
@login_required(login_url="landing")
@require_http_methods(["POST"])
def admin_resolve_score_anomaly_api(request, anomaly_id):
    """Mark a score anomaly as resolved."""
    err = _staff_json_required(request)
    if err:
        return err

    anomaly = get_object_or_404(CompositeScoreAnomaly, id=anomaly_id)
    if anomaly.is_resolved:
        return JsonResponse({"success": True, "already_resolved": True})

    anomaly.is_resolved = True
    anomaly.resolved_at = timezone.now()
    anomaly.resolved_by = request.user
    anomaly.save(update_fields=["is_resolved", "resolved_at", "resolved_by"])

    SystemAuditLog.objects.create(
        actor_user=request.user,
        actor_username=request.user.username,
        level="INFO",
        action="admin_score_anomaly_resolved",
        request_path=request.path,
        http_method=request.method,
        ip_address=request.META.get("REMOTE_ADDR"),
        metadata={
            "anomaly_id": anomaly.id,
            "restaurant_id": anomaly.restaurant_id,
            "anomaly_type": anomaly.anomaly_type,
        },
    )

    return JsonResponse({"success": True, "already_resolved": False})


# ---------------------------------------------------------------------------
#  Friend Chat  API
# ---------------------------------------------------------------------------


def _serialize_conversation(conv, request_user):
    """Serialize a FriendConversation to a JSON-safe dict."""
    participants = list(conv.get_participants().values_list("id", "username"))
    last_msg = conv.messages.order_by("-created_at").first()
    unread = conv.messages.filter(is_read=False).exclude(sender=request_user).count()

    other_username = None
    if not conv.is_group:
        for p in participants:
            if p[0] != request_user.id:
                other_username = p[1]
                break

    return {
        "id": conv.id,
        "name": conv.name,
        "is_group": conv.is_group,
        "creator_id": conv.creator_id,
        "other_username": other_username,
        "participants": [{"id": p[0], "username": p[1]} for p in participants],
        "unread_count": unread,
        "last_message": (
            {
                "body": last_msg.body or "",
                "sender_username": last_msg.sender.username,
                "created_at": last_msg.created_at.isoformat(),
            }
            if last_msg
            else None
        ),
        "updated_at": conv.updated_at.isoformat(),
    }


def _serialize_friend_message(msg):
    rec = msg.restaurant_recommendation
    return {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "sender_username": msg.sender.username,
        "body": msg.body or "",
        "restaurant_recommendation": (
            {
                "id": rec.id,
                "name": rec.name,
            }
            if rec
            else None
        ),
        "is_read": msg.is_read,
        "created_at": msg.created_at.isoformat(),
    }


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def friends_chat_list_api(request):
    """
    GET  → list current user's friend conversations (with unread counts).
    POST → start a new 1-on-1 conversation with a target username.
    """
    if request.method == "GET":
        convs = FriendConversation.objects.filter(participants=request.user).order_by(
            "-updated_at"
        )
        other_users = list(
            User.objects.filter(userprofile__role="diner")
            .exclude(id=request.user.id)
            .values("id", "username")
        )
        return JsonResponse(
            {
                "conversations": [
                    _serialize_conversation(c, request.user) for c in convs
                ],
                "other_users": other_users,
            }
        )

    # POST – start a new 1-on-1 conversation
    data = (
        json.loads(request.body)
        if request.content_type == "application/json"
        else request.POST
    )
    target_username = (data.get("username") or "").strip()

    if target_username == request.user.username:
        return _json_error("You cannot chat with yourself.", 400)

    target_user = User.objects.filter(
        username=target_username, userprofile__role="diner"
    ).first()
    if not target_user:
        return _json_error(f"User '{target_username}' not found.", 404)

    # Re-use existing 1-on-1 conversation
    user1, user2 = (
        (request.user, target_user)
        if request.user.id < target_user.id
        else (target_user, request.user)
    )
    conv = (
        FriendConversation.objects.filter(is_group=False)
        .filter(Q(user1=user1, user2=user2) | Q(user1=user2, user2=user1))
        .first()
    )
    if not conv:
        conv = FriendConversation.objects.create(
            user1=user1, user2=user2, is_group=False
        )
        conv.participants.add(user1, user2)

    return JsonResponse(
        {"conversation": _serialize_conversation(conv, request.user)}, status=201
    )


@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def friends_chat_detail_api(request, conversation_id):
    """
    GET  → messages + shared restaurants for a conversation.
    POST → send a new message.
    """
    conv = get_object_or_404(FriendConversation, id=conversation_id)
    if not conv.can_access(request.user):
        return _json_error("Access denied.", 403)

    if request.method == "GET":
        # Mark unread as read
        conv.messages.filter(is_read=False).exclude(sender=request.user).update(
            is_read=True
        )

        msgs = conv.messages.all().select_related("sender", "restaurant_recommendation")
        shared = conv.shared_restaurants.all().select_related("restaurant", "added_by")
        return JsonResponse(
            {
                "conversation": _serialize_conversation(conv, request.user),
                "messages": [_serialize_friend_message(m) for m in msgs],
                "shared_restaurants": [
                    {
                        "id": sr.id,
                        "restaurant_id": sr.restaurant_id,
                        "restaurant_name": sr.restaurant.name,
                        "added_by": sr.added_by.username,
                        "created_at": sr.created_at.isoformat(),
                    }
                    for sr in shared
                ],
            }
        )

    # POST – send a message
    data = (
        json.loads(request.body)
        if request.content_type == "application/json"
        else request.POST
    )
    body = (data.get("body") or "").strip()
    if not body:
        return _json_error("Message body is required.", 400)

    msg = FriendMessage.objects.create(
        conversation=conv, sender=request.user, body=body
    )
    conv.updated_at = timezone.now()
    conv.save(update_fields=["updated_at"])

    return JsonResponse({"message": _serialize_friend_message(msg)}, status=201)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def friends_chat_group_create_api(request):
    """
    POST → create a new group conversation.
    Body: { "name": "...", "participant_ids": [1, 2, ...] }
    """
    data = (
        json.loads(request.body)
        if request.content_type == "application/json"
        else request.POST
    )
    group_name = (data.get("name") or "").strip()
    if not group_name:
        return _json_error("Group name is required.", 400)

    participant_ids = data.get("participant_ids", [])
    if isinstance(participant_ids, str):
        participant_ids = json.loads(participant_ids)

    # Filter to only valid diner IDs
    valid_ids = []
    if participant_ids:
        valid_ids = list(
            User.objects.filter(id__in=participant_ids, userprofile__role="diner")
            .exclude(id=request.user.id)
            .values_list("id", flat=True)
        )

    if len(valid_ids) < 2:
        return _json_error("A group requires at least 2 other members.", 400)

    conv = FriendConversation.objects.create(
        name=group_name, is_group=True, creator=request.user
    )
    conv.participants.add(request.user)
    for p_id in valid_ids:
        conv.participants.add(p_id)

    return JsonResponse(
        {"conversation": _serialize_conversation(conv, request.user)}, status=201
    )


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def friends_chat_group_manage_api(request, conversation_id):
    """
    POST → add or remove a member from a group.
    Body: { "action": "add"|"remove", "user_id": 5 }
    """
    conv = get_object_or_404(FriendConversation, id=conversation_id, is_group=True)
    if conv.creator != request.user:
        return _json_error("Only the group creator can manage members.", 403)

    data = (
        json.loads(request.body)
        if request.content_type == "application/json"
        else request.POST
    )
    action = data.get("action")
    user_id = data.get("user_id")

    if action not in ("add", "remove"):
        return _json_error("action must be 'add' or 'remove'.", 400)

    target = User.objects.filter(id=user_id).first()
    if not target:
        return _json_error("User not found.", 404)

    if action == "add":
        if not (hasattr(target, "userprofile") and target.userprofile.role == "diner"):
            return _json_error("Only diners can be added to chat groups.", 400)

        if conv.participants.filter(id=target.id).exists():
            return _json_error(
                f"{target.username} is already a member of this group.", 400
            )

        conv.participants.add(target)
        return JsonResponse({"success": True, "detail": f"Added {target.username}."})

    # remove
    if target == conv.creator:
        return _json_error("Cannot remove the group creator.", 400)
    conv.participants.remove(target)
    return JsonResponse({"success": True, "detail": f"Removed {target.username}."})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def friends_chat_group_leave_api(request, conversation_id):
    """
    POST → leave a group conversation.
    """
    conv = get_object_or_404(FriendConversation, id=conversation_id, is_group=True)
    if not conv.can_access(request.user):
        return _json_error("Access denied.", 403)

    data = {}
    if request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            pass

    if conv.creator == request.user:
        new_admin_id = data.get("new_admin_id")
        if not new_admin_id:
            return _json_error(
                "Creators cannot leave their own groups without assigning a new admin.",
                400,
            )
        new_admin = conv.participants.filter(id=new_admin_id).first()
        if not new_admin or new_admin == request.user:
            return _json_error("Invalid new admin selected.", 400)

        conv.creator = new_admin
        conv.save()

    conv.participants.remove(request.user)
    return JsonResponse({"success": True, "detail": f"You have left '{conv.name}'."})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def friends_chat_recommend_api(request, conversation_id):
    """
    POST → send a restaurant recommendation to a conversation.
    Body: { "restaurant_id": 42, "body": "optional message" }
    """
    conv = get_object_or_404(FriendConversation, id=conversation_id)
    if not conv.can_access(request.user):
        return _json_error("Access denied.", 403)

    data = (
        json.loads(request.body)
        if request.content_type == "application/json"
        else request.POST
    )
    restaurant_id = data.get("restaurant_id")
    body = (data.get("body") or "").strip()

    restaurant = None
    if restaurant_id:
        restaurant = Restaurant.objects.filter(id=restaurant_id).first()
    if not restaurant:
        restaurant_name = (data.get("restaurant_name") or "").strip()
        if restaurant_name:
            restaurant = Restaurant.objects.filter(name=restaurant_name).first()
    if not restaurant:
        return _json_error("Restaurant not found.", 404)

    msg = FriendMessage.objects.create(
        conversation=conv,
        sender=request.user,
        body=body,
        restaurant_recommendation=restaurant,
    )
    conv.updated_at = timezone.now()
    conv.save(update_fields=["updated_at"])

    return JsonResponse({"message": _serialize_friend_message(msg)}, status=201)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def friends_chat_toggle_shared_api(request, conversation_id):
    """
    POST → add or remove a restaurant from the shared 'Together List'.
    Body: { "restaurant_id": 42, "action": "add"|"remove" }
    """
    conv = get_object_or_404(FriendConversation, id=conversation_id)
    if not conv.can_access(request.user):
        return _json_error("Access denied.", 403)

    data = (
        json.loads(request.body)
        if request.content_type == "application/json"
        else request.POST
    )
    restaurant_id = data.get("restaurant_id")
    action = data.get("action", "add")

    restaurant = None
    if restaurant_id:
        restaurant = Restaurant.objects.filter(id=restaurant_id).first()
    if not restaurant:
        restaurant_name = (data.get("restaurant_name") or "").strip()
        if restaurant_name:
            restaurant = Restaurant.objects.filter(name=restaurant_name).first()
    if not restaurant:
        return _json_error("Restaurant not found.", 404)

    if action == "add":
        FriendSharedRestaurant.objects.get_or_create(
            conversation=conv,
            restaurant=restaurant,
            defaults={"added_by": request.user},
        )
        return JsonResponse(
            {"success": True, "detail": f"Added {restaurant.name} to shared list."}
        )
    elif action == "remove":
        FriendSharedRestaurant.objects.filter(
            conversation=conv, restaurant=restaurant
        ).delete()
        return JsonResponse(
            {"success": True, "detail": f"Removed {restaurant.name} from shared list."}
        )
    else:
        return _json_error("action must be 'add' or 'remove'.", 400)


@login_required
def friends_chat_search_users_api(request):
    """
    GET → search for diners by username.
    Query: ?q=name
    """
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"users": []})

    users = User.objects.filter(
        username__icontains=q, userprofile__role="diner"
    ).exclude(id=request.user.id)[:10]

    return JsonResponse(
        {"users": [{"id": u.id, "username": u.username} for u in users]}
    )


@csrf_exempt
@login_required
@require_GET
def unread_counts_api(request):
    """GET → return total unread friend messages for the navbar badge."""
    total_unread = (
        FriendMessage.objects.filter(
            conversation__participants=request.user, is_read=False
        )
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({"total_unread": total_unread})
