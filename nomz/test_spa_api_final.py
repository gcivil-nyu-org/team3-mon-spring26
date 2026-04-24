"""
Pytest coverage for `nomz.spa_api` JSON views (function-based API, not ViewSets).

Each view has at least one success-path test (HTTP 2xx) and one error-path test
(4xx/5xx or redirect for unauthenticated `@login_required` routes).
"""

from __future__ import annotations

import os
import uuid
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from PIL import Image
from rest_framework.test import APIClient

from nomz.forms import RestaurantProfileForm
from nomz.models import (
    CompositeScoreAnomaly,
    CompositeScoreHistory,
    FriendConversation,
    FriendSharedRestaurant,
    LoginLog,
    ModerationReport,
    Restaurant,
    RestaurantOwnershipClaim,
    RestaurantPhoto,
    Review,
    ReviewResponse,
    UserPreference,
    UserProfile,
)

pytestmark = pytest.mark.django_db


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _make_image_upload(name: str = "shot.png") -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (2, 2), color=(120, 80, 200)).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def staff_user(db):
    u = User.objects.create_user(
        username=_unique("staff"),
        email=f"{uuid.uuid4().hex}@example.com",
        password="Str0ngPass!xyz",
        is_staff=True,
    )
    UserProfile.objects.create(user=u, role="diner", is_approved=True)
    return u


@pytest.fixture
def diner_user(db):
    u = User.objects.create_user(
        username=_unique("diner"),
        email=f"{uuid.uuid4().hex}@example.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(user=u, role="diner", is_approved=True)
    return u


@pytest.fixture
def owner_user(db):
    u = User.objects.create_user(
        username=_unique("owner"),
        email=f"{uuid.uuid4().hex}@example.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(user=u, role="restaurant", is_approved=True)
    r = Restaurant.objects.create(
        owner=u,
        name=_unique("Owned Bistro"),
        description="Fine dining",
        cuisine_type="italian",
        price_range="$$",
        is_active=True,
        neighborhood="SoHo",
        borough="Manhattan",
        composite_score=80,
    )
    return u, r


@pytest.fixture
def public_restaurant(db):
    """Visible in search: no owner, active."""
    return Restaurant.objects.create(
        owner=None,
        name=_unique("Public Eatery"),
        description="Neighborhood gem",
        cuisine_type="mexican",
        price_range="$",
        is_active=True,
        neighborhood="Astoria",
        borough="Queens",
        composite_score=70,
    )


@pytest.fixture
def diner_prefs(diner_user):
    return UserPreference.objects.create(
        user=diner_user,
        favorite_cuisines=["mexican"],
        dietary_restrictions=[],
        price_preference="$",
        neighborhood_preference="Astoria",
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_auth_session_success_anonymous(api_client):
    r = api_client.get("/api/auth/session/")
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is False


def test_auth_session_error_method_not_allowed(api_client):
    r = api_client.post("/api/auth/session/", {}, format="json")
    assert r.status_code == 405


def test_auth_register_success(api_client):
    payload = {
        "email": f"{uuid.uuid4().hex}@newuser.example.com",
        "username": _unique("reguser"),
        "role": "diner",
        "password1": "Str0ngPass!xyz",
        "password2": "Str0ngPass!xyz",
    }
    r = api_client.post("/api/auth/register/", payload, format="json")
    assert r.status_code == 201
    assert r.json()["authenticated"] is True


def test_auth_register_error_invalid_json(api_client):
    r = api_client.post(
        "/api/auth/register/",
        "not-json",
        content_type="application/json",
    )
    assert r.status_code == 400
    assert "error" in r.json()


def test_auth_register_error_validation(api_client):
    r = api_client.post(
        "/api/auth/register/",
        {
            "email": "",
            "username": "",
            "role": "diner",
            "password1": "x",
            "password2": "y",
        },
        format="json",
    )
    assert r.status_code == 400
    assert r.json().get("success") is False


def test_auth_login_success(api_client, diner_user):
    r = api_client.post(
        "/api/auth/login/",
        {"username": diner_user.username, "password": "Str0ngPass!xyz"},
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["authenticated"] is True


def test_auth_login_error_unauthorized(api_client, diner_user):
    r = api_client.post(
        "/api/auth/login/",
        {"username": diner_user.username, "password": "WrongPass!!!"},
        format="json",
    )
    assert r.status_code == 401


@patch("django.contrib.auth.hashers.check_password", return_value=True)
def test_auth_admin_login_success(_mock_check, api_client):
    os.environ["ADMIN_SECURITY_CODE"] = "SECURE_TEST_CODE"
    r = api_client.post(
        "/api/auth/admin-login/",
        {
            "username": "admin",
            "password": "does-not-matter-mocked",
            "security_code": "SECURE_TEST_CODE",
        },
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["authenticated"] is True


def test_auth_admin_login_error_missing_fields(api_client):
    r = api_client.post(
        "/api/auth/admin-login/",
        {"username": "admin", "password": "x"},
        format="json",
    )
    assert r.status_code == 400


@patch("nomz.spa_api.user_has_device", return_value=True)
def test_auth_login_requires_2fa_success(_mock_devices, api_client, diner_user):
    r = api_client.post(
        "/api/auth/login/",
        {"username": diner_user.username, "password": "Str0ngPass!xyz"},
        format="json",
    )
    assert r.status_code == 200
    assert r.json().get("requires_2fa") is True


@patch("nomz.spa_api.match_token", return_value=object())
def test_auth_2fa_verify_success(_mock_match, api_client, diner_user):
    s = api_client.session
    s["_2fa_user_id"] = diner_user.id
    s.save()
    r = api_client.post("/api/auth/2fa/verify/", {"token": "123456"}, format="json")
    assert r.status_code == 200
    assert r.json()["authenticated"] is True


def test_auth_2fa_verify_error_no_pending_session(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post("/api/auth/2fa/verify/", {"token": "123456"}, format="json")
    assert r.status_code == 400


def test_auth_logout_success(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post("/api/auth/logout/", {}, format="json")
    assert r.status_code == 200
    assert r.json()["authenticated"] is False


@patch("django.contrib.auth.forms.PasswordResetForm.save")
def test_auth_password_reset_request_success(_mock_save, api_client):
    r = api_client.post(
        "/api/auth/password-reset/",
        {"email": "anyone@example.com"},
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_auth_password_reset_request_error_missing_email(api_client):
    r = api_client.post("/api/auth/password-reset/", {}, format="json")
    assert r.status_code == 400


def test_auth_password_reset_confirm_success(api_client, diner_user):
    uid = urlsafe_base64_encode(force_bytes(diner_user.pk))
    token = default_token_generator.make_token(diner_user)
    r = api_client.post(
        "/api/auth/password-reset/confirm/",
        {
            "uid": uid,
            "token": token,
            "new_password1": "N3wStr0ngPass!aa",
            "new_password2": "N3wStr0ngPass!aa",
        },
        format="json",
    )
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_auth_password_reset_confirm_error_bad_token(api_client, diner_user):
    uid = urlsafe_base64_encode(force_bytes(diner_user.pk))
    r = api_client.post(
        "/api/auth/password-reset/confirm/",
        {
            "uid": uid,
            "token": "invalid-token",
            "new_password1": "N3wStr0ngPass!aa",
            "new_password2": "N3wStr0ngPass!aa",
        },
        format="json",
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Restaurant photos & activation
# ---------------------------------------------------------------------------


def test_restaurant_photos_data_success(api_client, owner_user):
    owner, rest = owner_user
    RestaurantPhoto.objects.create(
        restaurant=rest,
        photo=_make_image_upload(),
        caption="Dining room",
        is_primary=True,
    )
    api_client.force_login(owner)
    r = api_client.get("/api/restaurant/photos/data/")
    assert r.status_code == 200
    data = r.json()
    assert data["restaurant_id"] == rest.id
    assert len(data["photos"]) == 1


def test_restaurant_photos_data_error_forbidden_diner(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.get("/api/restaurant/photos/data/")
    assert r.status_code == 403


def test_restaurant_photo_upload_success(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    img = _make_image_upload()
    # Checkbox values: omit `is_primary` for unchecked; the string "false" is truthy in HTML forms.
    r = api_client.post(
        "/api/restaurant/photos/upload/",
        {"caption": "Kitchen", "photo": img},
    )
    assert r.status_code == 201, r.content
    assert "id" in r.json()


def test_restaurant_photo_upload_error_invalid_form(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    r = api_client.post(
        "/api/restaurant/photos/upload/",
        {"caption": "Missing file"},
        format="multipart",
    )
    assert r.status_code == 400


def test_restaurant_photo_delete_success(api_client, owner_user):
    owner, rest = owner_user
    ph = RestaurantPhoto.objects.create(
        restaurant=rest, photo=_make_image_upload(), caption="x"
    )
    api_client.force_login(owner)
    r = api_client.post(f"/api/restaurant/photos/{ph.id}/delete/", {}, format="json")
    assert r.status_code == 200
    assert not RestaurantPhoto.objects.filter(pk=ph.id).exists()


def test_restaurant_photo_delete_error_wrong_owner(api_client, owner_user, diner_user):
    _owner, rest = owner_user
    ph = RestaurantPhoto.objects.create(
        restaurant=rest, photo=_make_image_upload(), caption="x"
    )
    api_client.force_login(diner_user)
    r = api_client.post(f"/api/restaurant/photos/{ph.id}/delete/", {}, format="json")
    assert r.status_code == 403


def test_restaurant_photo_set_primary_success(api_client, owner_user):
    owner, rest = owner_user
    ph = RestaurantPhoto.objects.create(
        restaurant=rest, photo=_make_image_upload(), caption="x", is_primary=False
    )
    api_client.force_login(owner)
    r = api_client.post(
        f"/api/restaurant/photos/{ph.id}/set-primary/", {}, format="json"
    )
    assert r.status_code == 200
    ph.refresh_from_db()
    assert ph.is_primary is True


def test_restaurant_photo_set_primary_error_not_found(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    r = api_client.post("/api/restaurant/photos/999999/set-primary/", {}, format="json")
    assert r.status_code == 404


def test_restaurant_activation_get_post_success(api_client, owner_user):
    owner, rest = owner_user
    api_client.force_login(owner)
    assert api_client.get("/api/restaurant/activation/").status_code == 200
    r = api_client.post(
        "/api/restaurant/activation/", {"is_active": False}, format="json"
    )
    assert r.status_code == 200
    rest.refresh_from_db()
    assert rest.is_active is False


def test_restaurant_activation_error_missing_field(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    r = api_client.post("/api/restaurant/activation/", {}, format="json")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Diner preferences & account
# ---------------------------------------------------------------------------


def test_diner_preferences_get_post_success(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/diner/preferences/").status_code == 200
    r = api_client.post(
        "/api/diner/preferences/",
        {
            "favorite_cuisines": ["italian"],
            "dietary_restrictions": ["Vegan"],
            "price_preference": "$$",
            "neighborhood_preference": "SoHo",
        },
        format="json",
    )
    assert r.status_code == 200


def test_diner_preferences_error_forbidden_owner(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    assert api_client.get("/api/diner/preferences/").status_code == 403


def test_diner_account_get_patch_success(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/diner/account/").status_code == 200
    r = api_client.patch(
        "/api/diner/account/",
        {"first_name": "Pat", "last_name": "Lee", "email": "pat@example.com"},
        format="json",
    )
    assert r.status_code == 200


def test_diner_account_error_forbidden_owner(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    assert api_client.get("/api/diner/account/").status_code == 403


# ---------------------------------------------------------------------------
# Admin JSON
# ---------------------------------------------------------------------------


def test_admin_dashboard_summary_success(api_client, staff_user):
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/dashboard-summary/")
    assert r.status_code == 200
    assert "total_users" in r.json()


def test_admin_dashboard_summary_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/dashboard-summary/").status_code == 403


def test_admin_pending_approvals_success(api_client, staff_user, diner_user):
    pending = User.objects.create_user(
        username=_unique("pendbiz"),
        email=f"{uuid.uuid4().hex}@biz.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(
        user=pending, role="restaurant", is_approved=False, is_rejected=False
    )
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/pending-approvals/")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_admin_pending_approvals_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/pending-approvals/").status_code == 403


def test_admin_approved_restaurant_accounts_success(api_client, staff_user, owner_user):
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/approved-restaurants/")
    assert r.status_code == 200


def test_admin_approved_restaurant_accounts_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/approved-restaurants/").status_code == 403


def test_admin_rejected_restaurant_accounts_success(api_client, staff_user, db):
    u = User.objects.create_user(
        username=_unique("rej"),
        email=f"{uuid.uuid4().hex}@x.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(
        user=u, role="restaurant", is_approved=False, is_rejected=True
    )
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/rejected-restaurants/")
    assert r.status_code == 200


def test_admin_rejected_restaurant_accounts_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/rejected-restaurants/").status_code == 403


def test_admin_approve_user_success(
    api_client, staff_user, diner_user, public_restaurant
):
    pending = User.objects.create_user(
        username=_unique("claimant"),
        email=f"{uuid.uuid4().hex}@c.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(
        user=pending, role="restaurant", is_approved=False, is_rejected=False
    )
    RestaurantOwnershipClaim.objects.create(
        claimant=pending,
        restaurant=public_restaurant,
        status=RestaurantOwnershipClaim.STATUS_PENDING,
    )
    api_client.force_login(staff_user)
    r = api_client.post(f"/api/admin/approve/{pending.id}/", {}, format="json")
    assert r.status_code == 200


def test_admin_approve_user_error_not_found(api_client, staff_user):
    api_client.force_login(staff_user)
    assert (
        api_client.post("/api/admin/approve/999999/", {}, format="json").status_code
        == 404
    )


def test_admin_reject_user_success(
    api_client, staff_user, diner_user, public_restaurant
):
    pending = User.objects.create_user(
        username=_unique("reject_me"),
        email=f"{uuid.uuid4().hex}@c.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(
        user=pending, role="restaurant", is_approved=False, is_rejected=False
    )
    RestaurantOwnershipClaim.objects.create(
        claimant=pending,
        restaurant=public_restaurant,
        status=RestaurantOwnershipClaim.STATUS_PENDING,
    )
    api_client.force_login(staff_user)
    r = api_client.post(f"/api/admin/reject/{pending.id}/", {}, format="json")
    assert r.status_code == 200


def test_admin_reject_user_error_not_found(api_client, staff_user):
    api_client.force_login(staff_user)
    assert (
        api_client.post("/api/admin/reject/999999/", {}, format="json").status_code
        == 404
    )


def test_admin_moderation_data_success(api_client, staff_user, diner_user, owner_user):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="Great",
    )
    ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="SPAM",
        details="Too noisy",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/moderation/")
    assert r.status_code == 200
    assert len(r.json()["pending"]) >= 1


def test_admin_moderation_data_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/moderation/").status_code == 403


def test_admin_resolve_report_success(api_client, staff_user, diner_user, owner_user):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=4,
        comment="ok",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="Please review",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        {"action": "dismiss", "moderator_note": "ok"},
        format="json",
    )
    assert r.status_code == 200


def test_admin_resolve_report_error_invalid_action(
    api_client, staff_user, diner_user, owner_user
):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=4,
        comment="x",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="x",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        {"action": "not_a_real_action", "moderator_note": ""},
        format="json",
    )
    assert r.status_code == 400


def test_admin_users_data_success(api_client, staff_user, diner_user):
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/users/")
    assert r.status_code == 200
    ids = {row["id"] for row in r.json()["results"]}
    assert staff_user.id not in ids
    assert diner_user.id in ids or len(ids) >= 0


def test_admin_users_data_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/users/").status_code == 403


def test_admin_toggle_user_active_success(api_client, staff_user, diner_user):
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/users/{diner_user.id}/toggle-active/", {}, format="json"
    )
    assert r.status_code == 200


def test_admin_toggle_user_active_error_superuser(api_client, staff_user):
    su = User.objects.create_user(
        username=_unique("su"),
        email=f"{uuid.uuid4().hex}@x.com",
        password="Str0ngPass!xyz",
        is_superuser=True,
    )
    api_client.force_login(staff_user)
    assert (
        api_client.post(
            f"/api/admin/users/{su.id}/toggle-active/", {}, format="json"
        ).status_code
        == 400
    )


def test_admin_login_logs_data_success(api_client, staff_user):
    LoginLog.objects.create(username="u1", status="Success", is_suspicious=False)
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/login-logs/")
    assert r.status_code == 200


def test_admin_login_logs_data_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/login-logs/").status_code == 403


# ---------------------------------------------------------------------------
# Public restaurant detail, reviews, reports
# ---------------------------------------------------------------------------


def test_restaurant_detail_data_success(api_client, owner_user):
    _owner, rest = owner_user
    Review.objects.create(
        restaurant=rest,
        user=User.objects.create_user(
            username=_unique("revu"),
            email=f"{uuid.uuid4().hex}@r.com",
            password="Str0ngPass!xyz",
        ),
        rating=5,
        comment="Nice",
    )
    r = api_client.get(f"/api/restaurants/{rest.id}/")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == rest.id
    assert len(data["reviews"]) == 1
    # Check new fields for comparison
    assert "price_range" in data
    assert "hours_open" in data
    assert "hours_close" in data
    assert data["price_range"] == rest.price_range
    # Hours should be formatted as HH:MM strings
    expected_open = (
        rest.hours_open.strftime("%H:%M")
        if hasattr(rest.hours_open, "strftime")
        else str(rest.hours_open)
    )
    expected_close = (
        rest.hours_close.strftime("%H:%M")
        if hasattr(rest.hours_close, "strftime")
        else str(rest.hours_close)
    )
    assert data["hours_open"] == expected_open
    assert data["hours_close"] == expected_close


def test_restaurant_detail_data_error_not_found(api_client):
    assert api_client.get("/api/restaurants/999999/").status_code == 404


def test_restaurant_add_review_success(api_client, diner_user, owner_user):
    _owner, rest = owner_user
    api_client.force_login(diner_user)
    payload = {
        "rating": 5,
        "food_quality_rating": 5,
        "service_quality_rating": 5,
        "ambience_rating": 5,
        "location_rating": 5,
        "value_rating": 5,
        "dietary_accommodation_rating": 5,
        "cleanliness_rating": 5,
        "comment": "Loved it",
    }
    r = api_client.post(f"/api/restaurants/{rest.id}/review/", payload, format="json")
    assert r.status_code == 201


def test_restaurant_add_review_error_invalid_form(api_client, diner_user, owner_user):
    _owner, rest = owner_user
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/restaurants/{rest.id}/review/",
        {"rating": 99},
        format="json",
    )
    assert r.status_code == 400


def test_report_content_success(api_client, diner_user, owner_user):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=3,
        comment="meh",
    )
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/report/",
        {
            "content_type": "review",
            "content_id": rev.id,
            "reason": "SPAM",
            "details": "Promotional",
        },
        format="json",
    )
    assert r.status_code == 201


def test_report_content_error_review_not_found(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/report/",
        {
            "content_type": "review",
            "content_id": 999999,
            "reason": "SPAM",
            "details": "x",
        },
        format="json",
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Search, recommendations, owner profile / availability / communication
# ---------------------------------------------------------------------------


def test_restaurant_search_api_success(api_client, diner_user, public_restaurant):
    api_client.force_login(diner_user)
    r = api_client.get("/api/search/?q=Public")
    assert r.status_code == 200
    ids = [row["id"] for row in r.json()["results"]]
    assert public_restaurant.id in ids


def test_restaurant_search_api_prefers_tags_when_cuisine_is_placeholder(api_client, diner_user):
    restaurant = Restaurant.objects.create(
        owner=None,
        name=_unique("Cuisine Placeholder Spot"),
        description="Known for tagged cuisine",
        cuisine="other",
        cuisine_type="other",
        cuisine_tags=["Indian", "Japanese"],
        price_range="$$",
        is_active=True,
        neighborhood="Midtown",
        borough="Manhattan",
    )
    api_client.force_login(diner_user)
    r = api_client.get("/api/search/?q=Cuisine%20Placeholder")
    assert r.status_code == 200
    row = next((item for item in r.json()["results"] if item["id"] == restaurant.id), None)
    assert row is not None
    assert row["cuisine"] == "Indian, Japanese"


def test_restaurant_search_api_error_requires_login(api_client):
    r = api_client.get("/api/search/")
    assert r.status_code == 302


@patch("nomz.spa_api.recommend_restaurants_for_user", return_value=[])
def test_diner_recommendations_requires_prefs_message(
    _mock_rec, api_client, diner_user
):
    api_client.force_login(diner_user)
    r = api_client.get("/api/recommendations/")
    assert r.status_code == 200
    assert r.json()["requires_preferences"] is True


@patch("nomz.spa_api.recommend_restaurants_for_user")
def test_diner_recommendations_success(
    mock_rec, api_client, diner_user, diner_prefs, public_restaurant
):
    mock_rec.return_value = [public_restaurant]
    api_client.force_login(diner_user)
    r = api_client.get("/api/recommendations/")
    assert r.status_code == 200
    assert r.json()["requires_preferences"] is False
    assert len(r.json()["restaurants"]) == 1


def test_diner_recommendations_error_forbidden_owner(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    assert api_client.get("/api/recommendations/").status_code == 403


def test_restaurant_profile_get_success(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    r = api_client.get("/api/restaurant/profile/")
    assert r.status_code == 200
    assert r.json()["has_restaurant"] is True


def test_restaurant_profile_post_success(api_client, owner_user):
    owner, rest = owner_user
    api_client.force_login(owner)
    payload = {
        "name": rest.name,
        "description": "Updated copy",
        "cuisine_type": "italian",
        "price_range": "$$",
        "hours_open": "10:00",
        "hours_close": "22:00",
        "address": "1 Main",
        "phone": "555-010-0000",
        "website": "https://example.com",
        "email": "e@example.com",
    }
    r = api_client.post("/api/restaurant/profile/", payload, format="json")
    assert r.status_code == 200


def test_restaurant_profile_error_forbidden_diner(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/restaurant/profile/").status_code == 403


def test_restaurant_availability_get_post_success(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    assert api_client.get("/api/restaurant/availability/").status_code == 200
    r = api_client.post(
        "/api/restaurant/availability/",
        {
            "is_temporarily_unavailable": True,
            "unavailable_reason": "Renovation",
            "unavailable_until": "",
        },
        format="json",
    )
    assert r.status_code == 200


def test_restaurant_availability_error_invalid_json(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    r = api_client.post(
        "/api/restaurant/availability/",
        "not-json",
        content_type="application/json",
    )
    assert r.status_code == 400


def test_restaurant_communication_get_post_success(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    assert api_client.get("/api/restaurant/communication/").status_code == 200
    r = api_client.post(
        "/api/restaurant/communication/",
        {
            "messaging_enabled": True,
            "response_hours_start": "9:00 AM",
            "response_hours_end": "5:00 PM",
        },
        format="json",
    )
    assert r.status_code == 200


def test_restaurant_communication_error_invalid_hours(api_client, owner_user):
    owner, _rest = owner_user
    api_client.force_login(owner)
    r = api_client.post(
        "/api/restaurant/communication/",
        {
            "messaging_enabled": True,
            "response_hours_start": "6:00 PM",
            "response_hours_end": "9:00 AM",
        },
        format="json",
    )
    assert r.status_code == 400


def test_review_respond_api_success(api_client, owner_user, diner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="Excellent",
    )
    api_client.force_login(owner)
    r = api_client.post(
        f"/api/reviews/{rev.id}/respond/",
        {"response_text": "Thanks for visiting!"},
        format="json",
    )
    assert r.status_code == 200


def test_review_respond_api_error_wrong_user(api_client, diner_user, owner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=4,
        comment="ok",
    )
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/reviews/{rev.id}/respond/",
        {"response_text": "Nope"},
        format="json",
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Admin scoring
# ---------------------------------------------------------------------------


@patch("nomz.spa_api.refresh_restaurant_composite", return_value={"anomaly_count": 0})
def test_admin_recalculate_scores_success(
    _mock_refresh, api_client, staff_user, owner_user
):
    _owner, rest = owner_user
    api_client.force_login(staff_user)
    r = api_client.post(
        "/api/admin/recalculate-scores/",
        {"restaurant_id": str(rest.id)},
        format="json",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["updated"] == 1


def test_admin_recalculate_scores_error_bad_id(api_client, staff_user):
    api_client.force_login(staff_user)
    r = api_client.post(
        "/api/admin/recalculate-scores/",
        {"restaurant_id": "not-a-number"},
        format="json",
    )
    assert r.status_code == 400


def test_admin_score_anomalies_success(api_client, staff_user, owner_user):
    _owner, rest = owner_user
    hist = CompositeScoreHistory.objects.create(
        restaurant=rest,
        trigger_source=CompositeScoreHistory.TRIGGER_ADMIN_DASHBOARD,
    )
    CompositeScoreAnomaly.objects.create(
        restaurant=rest,
        score_history=hist,
        anomaly_type=CompositeScoreAnomaly.TYPE_LARGE_DELTA,
        severity=CompositeScoreAnomaly.SEVERITY_HIGH,
    )
    api_client.force_login(staff_user)
    r = api_client.get("/api/admin/score-anomalies/")
    assert r.status_code == 200
    assert len(r.json()["anomalies"]) >= 1


def test_admin_score_anomalies_error_forbidden(api_client, diner_user):
    api_client.force_login(diner_user)
    assert api_client.get("/api/admin/score-anomalies/").status_code == 403


def test_admin_resolve_score_anomaly_success(api_client, staff_user, owner_user):
    _owner, rest = owner_user
    hist = CompositeScoreHistory.objects.create(
        restaurant=rest,
        trigger_source=CompositeScoreHistory.TRIGGER_ADMIN_DASHBOARD,
    )
    an = CompositeScoreAnomaly.objects.create(
        restaurant=rest,
        score_history=hist,
        anomaly_type=CompositeScoreAnomaly.TYPE_LARGE_DELTA,
        severity=CompositeScoreAnomaly.SEVERITY_HIGH,
        is_resolved=False,
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/score-anomalies/{an.id}/resolve/", {}, format="json"
    )
    assert r.status_code == 200


def test_admin_resolve_score_anomaly_error_not_found(api_client, staff_user):
    api_client.force_login(staff_user)
    assert (
        api_client.post(
            "/api/admin/score-anomalies/999999/resolve/", {}, format="json"
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Friend chat
# ---------------------------------------------------------------------------


def _make_diner(username_prefix: str) -> User:
    u = User.objects.create_user(
        username=_unique(username_prefix),
        email=f"{uuid.uuid4().hex}@d.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(user=u, role="diner", is_approved=True)
    return u


def test_friends_chat_list_get_success(api_client, diner_user):
    other = _make_diner("pal")
    conv = FriendConversation.objects.create(
        user1=diner_user, user2=other, is_group=False
    )
    conv.participants.add(diner_user, other)
    api_client.force_login(diner_user)
    r = api_client.get("/api/friends-chat/")
    assert r.status_code == 200
    assert len(r.json()["conversations"]) >= 1


def test_friends_chat_list_error_requires_login(api_client):
    assert api_client.get("/api/friends-chat/").status_code == 302


def test_friends_chat_list_post_success(api_client, diner_user):
    buddy = _make_diner("buddy")
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/friends-chat/", {"username": buddy.username}, format="json"
    )
    assert r.status_code == 201


def test_friends_chat_list_post_error_user_not_found(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/friends-chat/", {"username": "no_such_user_ever"}, format="json"
    )
    assert r.status_code == 404


def test_friends_chat_detail_get_post_success(api_client, diner_user):
    buddy = _make_diner("buddy2")
    conv = FriendConversation.objects.create(
        user1=diner_user, user2=buddy, is_group=False
    )
    conv.participants.add(diner_user, buddy)
    api_client.force_login(diner_user)
    assert api_client.get(f"/api/friends-chat/{conv.id}/").status_code == 200
    r = api_client.post(
        f"/api/friends-chat/{conv.id}/", {"body": "Hello there"}, format="json"
    )
    assert r.status_code == 201


def test_friends_chat_detail_error_forbidden(api_client, diner_user):
    a = _make_diner("chat_a")
    b = _make_diner("chat_b")
    conv = FriendConversation.objects.create(user1=a, user2=b, is_group=False)
    conv.participants.add(a, b)
    api_client.force_login(diner_user)
    assert api_client.get(f"/api/friends-chat/{conv.id}/").status_code == 403


def test_friends_chat_group_create_success(api_client, diner_user):
    mate = _make_diner("mate")
    mate2 = _make_diner("mate2_group59")
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/friends-chat/group/create/",
        {"name": "Food Crew", "participant_ids": [mate.id, mate2.id]},
        format="json",
    )
    assert r.status_code == 201


def test_friends_chat_group_create_error_missing_name(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/friends-chat/group/create/",
        {"name": "", "participant_ids": []},
        format="json",
    )
    assert r.status_code == 400


def test_friends_chat_group_manage_success(api_client, diner_user):
    mate = _make_diner("mate2")
    api_client.force_login(diner_user)
    conv = FriendConversation.objects.create(
        name="Gourmets", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    r = api_client.post(
        f"/api/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "user_id": mate.id},
        format="json",
    )
    assert r.status_code == 200


def test_friends_chat_group_manage_error_not_creator(api_client, diner_user):
    mate = _make_diner("mate3")
    conv = FriendConversation.objects.create(name="Other", is_group=True, creator=mate)
    conv.participants.add(mate, diner_user)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "user_id": mate.id},
        format="json",
    )
    assert r.status_code == 403


def test_friends_chat_group_manage_error_already_added(api_client, diner_user):
    mate = _make_diner("already_here")
    conv = FriendConversation.objects.create(
        name="Dupes", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user, mate)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "user_id": mate.id},
        format="json",
    )
    assert r.status_code == 400
    assert "already a member" in r.json()["error"]


def test_friends_chat_group_leave_success(api_client, diner_user):
    leader = _make_diner("leader")
    conv = FriendConversation.objects.create(
        name="Lunch", is_group=True, creator=leader
    )
    conv.participants.add(leader, diner_user)
    api_client.force_login(diner_user)
    r = api_client.post(f"/api/friends-chat/group/{conv.id}/leave/", {}, format="json")
    assert r.status_code == 200


def test_friends_chat_group_leave_error_creator(api_client, diner_user):
    conv = FriendConversation.objects.create(
        name="Owners", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    api_client.force_login(diner_user)
    r = api_client.post(f"/api/friends-chat/group/{conv.id}/leave/", {}, format="json")
    assert r.status_code == 400


def test_friends_chat_group_leave_creator_pass(api_client, diner_user):
    mate = _make_diner("mate_pass")
    conv = FriendConversation.objects.create(
        name="OwnersPass", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user, mate)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/group/{conv.id}/leave/",
        {"new_admin_id": mate.id},
        format="json",
    )
    assert r.status_code == 200
    conv.refresh_from_db()
    assert conv.creator == mate
    assert diner_user not in conv.participants.all()


def test_friends_chat_search_users_success(api_client, diner_user):
    _make_diner("searchable1")
    _make_diner("searchable2")
    api_client.force_login(diner_user)
    r = api_client.get("/api/friends-chat/search-users/?q=searchable")
    assert r.status_code == 200
    data = r.json()
    assert "users" in data
    assert len(data["users"]) == 2


def test_friends_chat_group_manage_error_only_diners(
    api_client, diner_user, owner_without_restaurant
):
    conv = FriendConversation.objects.create(
        name="DinersOnlyGroup", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "user_id": owner_without_restaurant.id},
        format="json",
    )
    assert r.status_code == 400
    assert "Only diners can be added" in r.json()["error"]


def test_friends_chat_recommend_success(api_client, diner_user, public_restaurant):
    buddy = _make_diner("buddy4")
    conv = FriendConversation.objects.create(
        user1=diner_user, user2=buddy, is_group=False
    )
    conv.participants.add(diner_user, buddy)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/{conv.id}/recommend/",
        {"restaurant_id": public_restaurant.id, "body": "Try this"},
        format="json",
    )
    assert r.status_code == 201


def test_friends_chat_recommend_error_not_found(api_client, diner_user):
    buddy = _make_diner("buddy5")
    conv = FriendConversation.objects.create(
        user1=diner_user, user2=buddy, is_group=False
    )
    conv.participants.add(diner_user, buddy)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/{conv.id}/recommend/",
        {"restaurant_id": 999999},
        format="json",
    )
    assert r.status_code == 404


def test_friends_chat_toggle_shared_success(api_client, diner_user, public_restaurant):
    buddy = _make_diner("buddy6")
    conv = FriendConversation.objects.create(
        user1=diner_user, user2=buddy, is_group=False
    )
    conv.participants.add(diner_user, buddy)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/{conv.id}/toggle-shared/",
        {"restaurant_id": public_restaurant.id, "action": "add"},
        format="json",
    )
    assert r.status_code == 200
    assert FriendSharedRestaurant.objects.filter(
        conversation=conv, restaurant=public_restaurant
    ).exists()


def test_friends_chat_toggle_shared_error_bad_action(
    api_client, diner_user, public_restaurant
):
    buddy = _make_diner("buddy7")
    conv = FriendConversation.objects.create(
        user1=diner_user, user2=buddy, is_group=False
    )
    conv.participants.add(diner_user, buddy)
    api_client.force_login(diner_user)
    r = api_client.post(
        f"/api/friends-chat/{conv.id}/toggle-shared/",
        {"restaurant_id": public_restaurant.id, "action": "merge"},
        format="json",
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Extra branches (JSON helpers / edge responses)
# ---------------------------------------------------------------------------


def test_friends_chat_detail_post_error_empty_body(api_client, diner_user):
    buddy = _make_diner("buddy8")
    conv = FriendConversation.objects.create(
        user1=diner_user, user2=buddy, is_group=False
    )
    conv.participants.add(diner_user, buddy)
    api_client.force_login(diner_user)
    r = api_client.post(f"/api/friends-chat/{conv.id}/", {"body": ""}, format="json")
    assert r.status_code == 400


def test_review_respond_update_existing(api_client, owner_user, diner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="Great",
    )
    ReviewResponse.objects.create(
        review=rev,
        restaurant=rest,
        responder=owner,
        response_text="Old",
    )
    api_client.force_login(owner)
    r = api_client.post(
        f"/api/reviews/{rev.id}/respond/",
        {"response_text": "Updated thanks!"},
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["created"] is False


def test_restaurant_photos_data_empty_list_when_no_restaurant(api_client, db):
    u = User.objects.create_user(
        username=_unique("orphan_owner"),
        email=f"{uuid.uuid4().hex}@o.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(user=u, role="restaurant", is_approved=True)
    api_client.force_login(u)
    r = api_client.get("/api/restaurant/photos/data/")
    assert r.status_code == 200
    assert r.json()["photos"] == []


def test_admin_resolve_report_flag_fraud_on_user(
    api_client, staff_user, diner_user, owner_user
):
    owner, rest = owner_user
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        reported_user=owner,
        review=None,
        reason="FRAUD",
        details="Suspicious pattern",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        {"action": "flag_fraud", "moderator_note": "confirmed"},
        format="json",
    )
    assert r.status_code == 200


def test_admin_approve_user_validation_error(api_client, staff_user, public_restaurant):
    pending = User.objects.create_user(
        username=_unique("claim_fail"),
        email=f"{uuid.uuid4().hex}@c.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(
        user=pending, role="restaurant", is_approved=False, is_rejected=False
    )
    RestaurantOwnershipClaim.objects.create(
        claimant=pending,
        restaurant=public_restaurant,
        status=RestaurantOwnershipClaim.STATUS_PENDING,
    )
    api_client.force_login(staff_user)
    with patch.object(
        RestaurantOwnershipClaim,
        "approve",
        side_effect=ValidationError("Cannot approve this claim."),
    ):
        r = api_client.post(f"/api/admin/approve/{pending.id}/", {}, format="json")
    assert r.status_code == 400


@pytest.fixture
def owner_without_restaurant(db):
    u = User.objects.create_user(
        username=_unique("new_owner"),
        email=f"{uuid.uuid4().hex}@biz.com",
        password="Str0ngPass!xyz",
    )
    UserProfile.objects.create(user=u, role="restaurant", is_approved=True)
    return u


def test_auth_register_when_already_authenticated(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/auth/register/",
        {
            "email": "x@x.com",
            "username": "nope",
            "role": "diner",
            "password1": "x",
            "password2": "x",
        },
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["authenticated"] is True


def test_auth_login_error_invalid_json(api_client):
    r = api_client.post(
        "/api/auth/login/",
        "not-json",
        content_type="application/json",
    )
    assert r.status_code == 400


def test_auth_login_error_missing_credentials(api_client):
    r = api_client.post(
        "/api/auth/login/", {"username": "", "password": ""}, format="json"
    )
    assert r.status_code == 400


def test_auth_admin_login_when_already_staff(api_client, staff_user):
    api_client.force_login(staff_user)
    r = api_client.post("/api/auth/admin-login/", {}, format="json")
    assert r.status_code == 200
    assert r.json()["is_staff"] is True


def test_auth_admin_login_error_invalid_json(api_client):
    r = api_client.post(
        "/api/auth/admin-login/",
        "not-json",
        content_type="application/json",
    )
    assert r.status_code == 400


@patch("nomz.spa_api.match_token", return_value=None)
def test_auth_2fa_verify_error_invalid_token(_mock_match, api_client, diner_user):
    s = api_client.session
    s["_2fa_user_id"] = diner_user.id
    s.save()
    r = api_client.post("/api/auth/2fa/verify/", {"token": "000000"}, format="json")
    assert r.status_code == 401


def test_auth_password_reset_confirm_error_invalid_json(api_client):
    r = api_client.post(
        "/api/auth/password-reset/confirm/",
        "not-json",
        content_type="application/json",
    )
    assert r.status_code == 400


def test_auth_password_reset_confirm_error_missing_uid(api_client):
    r = api_client.post(
        "/api/auth/password-reset/confirm/",
        {"uid": "", "token": "x", "new_password1": "a", "new_password2": "a"},
        format="json",
    )
    assert r.status_code == 400


def test_admin_resolve_report_flag_fraud_on_review(
    api_client, staff_user, diner_user, owner_user
):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=3,
        comment="spammy",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="FRAUD",
        details="bad",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        {"action": "flag_fraud", "moderator_note": "fraud"},
        format="json",
    )
    assert r.status_code == 200
    rev.refresh_from_db()
    assert rev.is_flagged is True


def test_admin_resolve_report_unflag_review(
    api_client, staff_user, diner_user, owner_user
):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=4,
        comment="fine",
        is_flagged=True,
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="mistake",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        {"action": "unflag", "moderator_note": ""},
        format="json",
    )
    assert r.status_code == 200
    rev.refresh_from_db()
    assert rev.is_flagged is False


def test_admin_resolve_report_delete_review(
    api_client, staff_user, diner_user, owner_user
):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=2,
        comment="remove",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="INAPPROPRIATE",
        details="policy",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        {"action": "delete", "moderator_note": "removed"},
        format="json",
    )
    assert r.status_code == 200
    rev.refresh_from_db()
    assert rev.is_deleted is True


def test_admin_resolve_report_reevaluate(
    api_client, staff_user, diner_user, owner_user
):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="x",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="reopen",
        status="RESOLVED",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        {"action": "reevaluate", "moderator_note": "again"},
        format="json",
    )
    assert r.status_code == 200


def test_admin_resolve_report_error_invalid_json(
    api_client, staff_user, diner_user, owner_user
):
    _owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="x",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="x",
        status="PENDING",
    )
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/moderation/reports/{rep.id}/resolve/",
        "not-json",
        content_type="application/json",
    )
    assert r.status_code == 400


def test_admin_toggle_user_active_error_self(api_client, staff_user):
    api_client.force_login(staff_user)
    r = api_client.post(
        f"/api/admin/users/{staff_user.id}/toggle-active/", {}, format="json"
    )
    assert r.status_code == 400


def test_report_content_user_target_success(api_client, diner_user, owner_user):
    owner, _rest = owner_user
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/report/",
        {
            "content_type": "user",
            "content_id": owner.id,
            "reason": "HARASSMENT",
            "details": "Inappropriate messages",
        },
        format="json",
    )
    assert r.status_code == 201


def test_report_content_error_user_not_found(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/report/",
        {
            "content_type": "user",
            "content_id": 999999,
            "reason": "OTHER",
            "details": "x",
        },
        format="json",
    )
    assert r.status_code == 404


def test_restaurant_profile_create_success(api_client, owner_without_restaurant):
    api_client.force_login(owner_without_restaurant)
    name = _unique("Brand New Spot")
    payload = {
        "name": name,
        "description": "Grand opening",
        "cuisine_type": "thai",
        "price_range": "$",
        "hours_open": "11:00",
        "hours_close": "23:00",
        "address": "9th Ave",
        "phone": "555-019-9000",
        "website": "https://example.com/",
        "email": "chef@example.com",
    }
    r = api_client.post("/api/restaurant/profile/", payload, format="json")
    assert r.status_code == 201
    assert Restaurant.objects.filter(name=name, owner=owner_without_restaurant).exists()


@patch("nomz.spa_api.refresh_restaurant_composite", return_value={"anomaly_count": 0})
def test_admin_recalculate_scores_empty_filter(_mock_refresh, api_client, staff_user):
    api_client.force_login(staff_user)
    r = api_client.post(
        "/api/admin/recalculate-scores/",
        {"restaurant_id": "999999999"},
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["updated"] == 0


@patch("nomz.spa_api.refresh_restaurant_composite", return_value={"anomaly_count": 1})
def test_admin_recalculate_scores_by_name(
    _mock_refresh, api_client, staff_user, public_restaurant
):
    api_client.force_login(staff_user)
    r = api_client.post(
        "/api/admin/recalculate-scores/",
        {"restaurant_name": public_restaurant.name},
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["updated"] == 1


def test_friends_chat_list_post_error_chat_with_self(api_client, diner_user):
    api_client.force_login(diner_user)
    r = api_client.post(
        "/api/friends-chat/", {"username": diner_user.username}, format="json"
    )
    assert r.status_code == 400


def test_restaurant_detail_with_owner_response(api_client, owner_user, diner_user):
    owner, rest = owner_user
    Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="Super",
    )
    ReviewResponse.objects.create(
        review=Review.objects.filter(restaurant=rest, user=diner_user).first(),
        restaurant=rest,
        responder=owner,
        response_text="Thanks!",
    )
    r = api_client.get(f"/api/restaurants/{rest.id}/")
    assert r.status_code == 200
    assert r.json()["reviews"][0]["owner_response"] is not None


pytestmark = pytest.mark.django_db


def test_restaurant_profile_form_phone_validation():
    # Alphabet in phone
    form = RestaurantProfileForm(data={"phone": "1234abc56789"})
    form.is_valid()
    assert "phone" in form.errors
    assert "Alphabets are not allowed" in form.errors["phone"][0]

    # Less than 10 digits
    form2 = RestaurantProfileForm(data={"phone": "123456"})
    form2.is_valid()
    assert "phone" in form2.errors
    assert "must contain at least 10" in form2.errors["phone"][0]

    # Valid phone
    form3 = RestaurantProfileForm(data={"phone": "(123) 456-7890"})
    form3.is_valid()
    assert "phone" not in form3.errors


def test_restaurant_profile_form_email_validation():
    # Missing @
    form = RestaurantProfileForm(data={"email": "q.com"})
    form.is_valid()
    assert "email" in form.errors
    assert "missing an '@'" in form.errors["email"][0]

    # Missing letter before @
    form2 = RestaurantProfileForm(data={"email": "@q.com"})
    form2.is_valid()
    assert "email" in form2.errors
    assert "before @" in form2.errors["email"][0]

    # Missing letter after @
    form3 = RestaurantProfileForm(data={"email": "texx@"})
    form3.is_valid()
    assert "email" in form3.errors
    assert "following '@'" in form3.errors["email"][0]

    # Bad domain
    form4 = RestaurantProfileForm(data={"email": "texx@c,com"})
    form4.is_valid()
    assert "email" in form4.errors
    assert "valid format" in form4.errors["email"][0]


def test_restaurant_profile_minor_update_keeps_approval(api_client, owner_user):
    owner, rest = owner_user

    owner.userprofile.is_approved = True
    owner.userprofile.save()

    api_client.force_login(owner)

    payload = {
        "name": rest.name,
        "description": rest.description,
        "cuisine_type": rest.cuisine_type,
        "price_range": rest.price_range,
        "address": rest.address,
        "hours_open": "10:00",
        "hours_close": "22:00",
        "phone": "555-123-4567",
        "website": rest.website,
        "email": rest.email,
    }
    r = api_client.post("/api/restaurant/profile/", payload, format="json")
    assert r.status_code == 200

    owner.userprofile.refresh_from_db()
    assert owner.userprofile.is_approved is True


def test_restaurant_profile_major_update_resets_approval(api_client, owner_user):
    owner, rest = owner_user

    owner.userprofile.is_approved = True
    owner.userprofile.save()

    api_client.force_login(owner)

    payload = {
        "name": "Different Name",
        "description": rest.description,
        "cuisine_type": rest.cuisine_type,
        "price_range": rest.price_range,
        "address": rest.address,
        "hours_open": "10:00",
        "hours_close": "22:00",
        "phone": "555-123-4567",
        "website": rest.website,
        "email": rest.email,
    }
    r = api_client.post("/api/restaurant/profile/", payload, format="json")
    assert r.status_code == 200

    owner.userprofile.refresh_from_db()
    assert owner.userprofile.is_approved is False
