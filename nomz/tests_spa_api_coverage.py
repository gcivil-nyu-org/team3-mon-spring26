import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient

from nomz.models import Restaurant, SystemAuditLog, UserProfile


pytestmark = pytest.mark.django_db


def _create_user(username: str, password: str = "pass12345", role: str = "diner", **kwargs):
    user = User.objects.create_user(username=username, password=password, **kwargs)
    UserProfile.objects.create(user=user, role=role)
    return user


def test_auth_password_reset_request_validation_and_success_paths():
    client = APIClient()

    invalid_json = client.post(
        "/api/auth/password-reset/",
        data="{not-json",
        content_type="application/json",
    )
    assert invalid_json.status_code == 400
    assert invalid_json.json()["error"] == "Invalid JSON."

    missing_email = client.post(
        "/api/auth/password-reset/",
        data=json.dumps({"email": "  "}),
        content_type="application/json",
    )
    assert missing_email.status_code == 400
    assert missing_email.json()["error"] == "Email is required."

    with patch("nomz.spa_api.PasswordResetForm.save") as mocked_save:
        valid = client.post(
            "/api/auth/password-reset/",
            data=json.dumps({"email": "known@example.com"}),
            content_type="application/json",
        )
        assert valid.status_code == 200
        assert valid.json()["success"] is True
        assert mocked_save.called


def test_auth_password_reset_confirm_error_and_form_invalid_paths():
    client = APIClient()

    invalid_json = client.post(
        "/api/auth/password-reset/confirm/",
        data="{bad-json",
        content_type="application/json",
    )
    assert invalid_json.status_code == 400
    assert invalid_json.json()["error"] == "Invalid JSON."

    missing_uid_token = client.post(
        "/api/auth/password-reset/confirm/",
        data=json.dumps(
            {"uid": "", "token": "", "new_password1": "abc123XYZ!", "new_password2": "abc123XYZ!"}
        ),
        content_type="application/json",
    )
    assert missing_uid_token.status_code == 400
    assert missing_uid_token.json()["error"] == "Invalid reset link."

    missing_passwords = client.post(
        "/api/auth/password-reset/confirm/",
        data=json.dumps({"uid": "abc", "token": "tok", "new_password1": "", "new_password2": ""}),
        content_type="application/json",
    )
    assert missing_passwords.status_code == 400
    assert missing_passwords.json()["error"] == "Both password fields are required."

    invalid_uid = client.post(
        "/api/auth/password-reset/confirm/",
        data=json.dumps(
            {"uid": "%%%invalid%%%", "token": "tok", "new_password1": "abc123XYZ!", "new_password2": "abc123XYZ!"}
        ),
        content_type="application/json",
    )
    assert invalid_uid.status_code == 400
    assert invalid_uid.json()["error"] == "Invalid reset link."

    user = _create_user("reset_user", email="reset@example.com")
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    bad_token = client.post(
        "/api/auth/password-reset/confirm/",
        data=json.dumps(
            {
                "uid": uid,
                "token": "not-a-valid-token",
                "new_password1": "abc123XYZ!",
                "new_password2": "abc123XYZ!",
            }
        ),
        content_type="application/json",
    )
    assert bad_token.status_code == 400
    assert bad_token.json()["expired"] is True

    good_token = default_token_generator.make_token(user)
    form_invalid = client.post(
        "/api/auth/password-reset/confirm/",
        data=json.dumps(
            {
                "uid": uid,
                "token": good_token,
                "new_password1": "abc123XYZ!",
                "new_password2": "mismatchXYZ!",
            }
        ),
        content_type="application/json",
    )
    assert form_invalid.status_code == 400
    assert form_invalid.json()["success"] is False
    assert "errors" in form_invalid.json()


def test_restaurant_activation_permission_denied_and_not_found():
    client = APIClient()

    diner = _create_user("diner_perm", role="diner")
    client.force_login(diner)
    denied = client.get("/api/restaurant/activation/")
    assert denied.status_code == 403
    assert denied.json()["error"] == "Restaurant owners only."

    owner_without_restaurant = _create_user("owner_no_rest", role="restaurant")
    client.force_login(owner_without_restaurant)
    not_found = client.get("/api/restaurant/activation/")
    assert not_found.status_code == 404


def test_admin_dashboard_summary_permission_denied_for_non_staff():
    client = APIClient()
    non_staff = _create_user("nonstaff_user", role="diner")
    client.force_login(non_staff)

    response = client.get("/api/admin/dashboard-summary/")
    assert response.status_code == 403
    assert response.json()["error"] == "Staff access required."


def test_admin_recalculate_scores_filtering_branches_and_success():
    client = APIClient()
    staff = User.objects.create_user(
        username="staff_recalc",
        password="pass12345",
        is_staff=True,
    )
    UserProfile.objects.create(user=staff, role="diner")
    client.force_login(staff)

    r1 = Restaurant.objects.create(name="Recalc Alpha", cuisine_type="other", price_range="$$")
    r2 = Restaurant.objects.create(name="Recalc Beta", cuisine_type="other", price_range="$$")
    Restaurant.objects.create(name="Twin Match", cuisine_type="other", price_range="$$")
    Restaurant.objects.create(name="twin match", cuisine_type="other", price_range="$$")
    Restaurant.objects.create(name="Partial A Item", cuisine_type="other", price_range="$$")
    Restaurant.objects.create(name="Partial B Item", cuisine_type="other", price_range="$$")

    invalid_json = client.post(
        "/api/admin/recalculate-scores/",
        data="{bad-json",
        content_type="application/json",
    )
    assert invalid_json.status_code == 400
    assert invalid_json.json()["error"] == "Invalid JSON."

    invalid_id = client.post(
        "/api/admin/recalculate-scores/",
        data=json.dumps({"restaurant_id": "abc"}),
        content_type="application/json",
    )
    assert invalid_id.status_code == 400
    assert invalid_id.json()["error"] == "Restaurant ID must be a number."

    duplicate_exact = client.post(
        "/api/admin/recalculate-scores/",
        data=json.dumps({"restaurant_name": "Twin Match"}),
        content_type="application/json",
    )
    assert duplicate_exact.status_code == 400
    assert duplicate_exact.json()["error"] == "Multiple restaurants share that name."

    duplicate_partial = client.post(
        "/api/admin/recalculate-scores/",
        data=json.dumps({"restaurant_name": "Partial"}),
        content_type="application/json",
    )
    assert duplicate_partial.status_code == 400
    assert duplicate_partial.json()["error"] == "Multiple restaurants match that name."

    not_found = client.post(
        "/api/admin/recalculate-scores/",
        data=json.dumps({"restaurant_name": "No Such Restaurant"}),
        content_type="application/json",
    )
    assert not_found.status_code == 404
    assert not_found.json()["error"] == "No restaurant found with that name."

    zero_total = client.post(
        "/api/admin/recalculate-scores/",
        data=json.dumps({"restaurant_id": str(r2.id + 99999)}),
        content_type="application/json",
    )
    assert zero_total.status_code == 200
    assert zero_total.json() == {"success": True, "updated": 0, "anomaly_count": 0, "total": 0}

    with patch(
        "nomz.spa_api.refresh_restaurant_composite",
        side_effect=[{"anomaly_count": 2}, {"anomaly_count": 1}],
    ) as mock_refresh:
        success = client.post(
            "/api/admin/recalculate-scores/",
            data=json.dumps({"restaurant_name": "Recalc"}),
            content_type="application/json",
        )
        assert success.status_code == 400  # partial name is multiple matches
        assert success.json()["error"] == "Multiple restaurants match that name."

        success = client.post(
            "/api/admin/recalculate-scores/",
            data=json.dumps({"restaurant_id": str(r1.id)}),
            content_type="application/json",
        )
        assert success.status_code == 200
        payload = success.json()
        assert payload["success"] is True
        assert payload["updated"] == 1
        assert payload["total"] == 1
        assert payload["anomaly_count"] == 2
        assert mock_refresh.call_count == 1
        assert SystemAuditLog.objects.filter(
            action="admin_composite_score_recalculation"
        ).exists()
