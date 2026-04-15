import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient

from nomz.models import (
    CompositeScoreAnomaly,
    CompositeScoreHistory,
    FriendConversation,
    FriendMessage,
    FriendSharedRestaurant,
    ModerationReport,
    Restaurant,
    Review,
    SystemAuditLog,
    UserPreference,
    UserProfile,
)


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


def test_admin_moderation_data_permission_and_payload_rows():
    client = APIClient()
    staff = _create_user("staff_mod_data", role="diner", is_staff=True)
    reporter = _create_user("reporter_mod_data", role="diner")

    denied_user = _create_user("non_staff_mod_data", role="diner")
    client.force_login(denied_user)
    denied = client.get("/api/admin/moderation/")
    assert denied.status_code == 403
    assert denied.json()["error"] == "Staff access required."

    restaurant = Restaurant.objects.create(name="Moderation Data Spot", cuisine_type="other", price_range="$$")
    review = Review.objects.create(restaurant=restaurant, user=reporter, rating=2, comment="flag me")
    ModerationReport.objects.create(
        reporter=reporter,
        review=review,
        reason="SPAM",
        details="pending case",
        status="PENDING",
    )
    ModerationReport.objects.create(
        reporter=reporter,
        review=review,
        reason="OTHER",
        details="resolved case",
        status="RESOLVED",
    )

    client.force_login(staff)
    response = client.get("/api/admin/moderation/")
    assert response.status_code == 200
    payload = response.json()
    assert "pending" in payload and "resolved" in payload
    assert payload["pending"][0]["reporter_username"] == reporter.username
    assert {"id", "reason", "details", "status", "created_at"}.issubset(
        set(payload["pending"][0].keys())
    )


def test_admin_resolve_report_api_unflag_paths_and_not_found():
    client = APIClient()
    staff = _create_user("staff_mod_unflag", role="diner", is_staff=True)
    reporter = _create_user("reporter_mod_unflag", role="diner")
    reported_user = _create_user("reported_mod_unflag", role="diner")
    owned_restaurant = Restaurant.objects.create(
        owner=reported_user,
        name="Reported Owner Spot",
        cuisine_type="other",
        price_range="$$",
        is_flagged=True,
    )
    reported_user.userprofile.is_flagged = True
    reported_user.userprofile.save(update_fields=["is_flagged"])

    client.force_login(staff)
    not_found = client.post(
        "/api/admin/moderation/reports/999999/resolve/",
        data=json.dumps({"action": "unflag"}),
        content_type="application/json",
    )
    assert not_found.status_code == 404

    report_user = ModerationReport.objects.create(
        reporter=reporter,
        reported_user=reported_user,
        reason="FRAUD",
        details="user branch",
        status="RESOLVED",
    )
    user_branch = client.post(
        f"/api/admin/moderation/reports/{report_user.id}/resolve/",
        data=json.dumps(
            {
                "action": "unflag",
                "moderator_note": "clear user",
                "nested_meta": {"actor": {"id": staff.id, "role": "staff"}},
            }
        ),
        content_type="application/json",
    )
    assert user_branch.status_code == 200
    report_user.refresh_from_db()
    reported_user.userprofile.refresh_from_db()
    owned_restaurant.refresh_from_db()
    assert report_user.status == "PENDING"
    assert reported_user.userprofile.is_flagged is False
    assert owned_restaurant.is_flagged is False

    review_restaurant = Restaurant.objects.create(
        name="Review Unflag Spot",
        cuisine_type="other",
        price_range="$$",
    )
    review = Review.objects.create(
        restaurant=review_restaurant,
        user=reporter,
        rating=3,
        is_flagged=True,
    )
    report_review = ModerationReport.objects.create(
        reporter=reporter,
        review=review,
        reason="SPAM",
        details="review branch",
        status="RESOLVED",
    )
    review_branch = client.post(
        f"/api/admin/moderation/reports/{report_review.id}/resolve/",
        data=json.dumps({"action": "unflag", "moderator_note": "clear review"}),
        content_type="application/json",
    )
    assert review_branch.status_code == 200
    review.refresh_from_db()
    report_review.refresh_from_db()
    assert review.is_flagged is False
    assert report_review.status == "PENDING"


def test_restaurant_availability_update_parses_unavailable_until_formats():
    client = APIClient()
    owner = _create_user("owner_availability_parse", role="restaurant")
    Restaurant.objects.create(
        owner=owner,
        name="Availability Parse Spot",
        cuisine_type="other",
        price_range="$$",
        is_active=True,
    )
    client.force_login(owner)

    response = client.post(
        "/api/restaurant/availability/",
        data=json.dumps(
            {
                "is_temporarily_unavailable": True,
                "unavailable_reason": "Kitchen maintenance",
                # Space-separated datetime exercises _parse_unavailable_until 1134-1141 path.
                "unavailable_until": "2026-04-17 13:45:00",
                "extra_nested": {"ops": {"ticket": 42, "severity": "high"}},
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["is_temporarily_unavailable"] is True
    assert payload["unavailable_until"]

    owner_without_restaurant = _create_user("owner_missing_rest", role="restaurant")
    client.force_login(owner_without_restaurant)
    not_found = client.post(
        "/api/restaurant/availability/",
        data=json.dumps({"is_temporarily_unavailable": True}),
        content_type="application/json",
    )
    assert not_found.status_code == 404


def test_diner_recommendations_permission_and_preference_branches():
    client = APIClient()

    owner = _create_user("non_diner_for_recs", role="restaurant")
    client.force_login(owner)
    denied = client.get("/api/recommendations/")
    assert denied.status_code == 403
    assert denied.json()["error"] == "Diners only."

    diner_no_prefs = _create_user("diner_no_prefs", role="diner")
    client.force_login(diner_no_prefs)
    no_prefs = client.get("/api/recommendations/")
    assert no_prefs.status_code == 200
    assert no_prefs.json()["requires_preferences"] is True

    diner_blank = _create_user("diner_blank_prefs", role="diner")
    UserPreference.objects.create(
        user=diner_blank,
        favorite_cuisines=[],
        dietary_restrictions=[],
        neighborhood_preference="",
        price_preference="",
    )
    client.force_login(diner_blank)
    blank_prefs = client.get("/api/recommendations/")
    assert blank_prefs.status_code == 200
    assert blank_prefs.json()["requires_preferences"] is True

    diner_with_prefs = _create_user("diner_with_prefs", role="diner")
    UserPreference.objects.create(
        user=diner_with_prefs,
        favorite_cuisines=["thai"],
        dietary_restrictions=[],
        neighborhood_preference="Queens",
        price_preference="$$",
    )
    client.force_login(diner_with_prefs)
    with patch("nomz.spa_api.recommend_restaurants_for_user", return_value=[]) as mock_recommend:
        no_match = client.get("/api/recommendations/")
        assert no_match.status_code == 200
        payload = no_match.json()
        assert payload["requires_preferences"] is False
        assert "No restaurants currently match your saved preferences" in payload["message"]
        assert payload["restaurants"] == []
        assert mock_recommend.called


def test_admin_resolve_score_anomaly_api_staff_gate_and_resolve_paths():
    client = APIClient()
    non_staff = _create_user("anom_non_staff", role="diner")
    staff = _create_user("anom_staff", role="diner", is_staff=True)
    restaurant = Restaurant.objects.create(
        name="Anomaly Spot",
        cuisine_type="other",
        price_range="$$",
    )
    score_history = CompositeScoreHistory.objects.create(
        restaurant=restaurant,
        trigger_source=CompositeScoreHistory.TRIGGER_OTHER,
        composite_score=80,
    )
    unresolved = CompositeScoreAnomaly.objects.create(
        restaurant=restaurant,
        score_history=score_history,
        anomaly_type=CompositeScoreAnomaly.TYPE_LARGE_DELTA,
        severity=CompositeScoreAnomaly.SEVERITY_HIGH,
        details={"delta": 20},
        is_resolved=False,
    )
    already_resolved = CompositeScoreAnomaly.objects.create(
        restaurant=restaurant,
        score_history=score_history,
        anomaly_type=CompositeScoreAnomaly.TYPE_LOW_CONFIDENCE_HIGH_SCORE,
        severity=CompositeScoreAnomaly.SEVERITY_MEDIUM,
        details={"confidence": 0.1},
        is_resolved=True,
    )

    client.force_login(non_staff)
    denied = client.post(f"/api/admin/score-anomalies/{unresolved.id}/resolve/")
    assert denied.status_code == 403
    assert denied.json()["error"] == "Staff access required."

    client.force_login(staff)
    already = client.post(f"/api/admin/score-anomalies/{already_resolved.id}/resolve/")
    assert already.status_code == 200
    assert already.json() == {"success": True, "already_resolved": True}

    resolved = client.post(f"/api/admin/score-anomalies/{unresolved.id}/resolve/")
    assert resolved.status_code == 200
    assert resolved.json() == {"success": True, "already_resolved": False}
    unresolved.refresh_from_db()
    assert unresolved.is_resolved is True
    assert unresolved.resolved_by_id == staff.id


def test_friends_chat_list_api_get_and_post_branch_conditions():
    client = APIClient()
    user = _create_user("chat_user", role="diner")
    other = _create_user("chat_other", role="diner")
    third = _create_user("chat_third", role="diner")
    convo = FriendConversation.objects.create(
        user1=user,
        user2=other,
        is_group=False,
    )
    convo.participants.add(user, other)
    FriendMessage.objects.create(conversation=convo, sender=other, body="hello", is_read=False)

    client.force_login(user)
    listing = client.get("/api/friends-chat/")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["conversations"]
    usernames = {u["username"] for u in payload["other_users"]}
    assert user.username not in usernames
    assert {other.username, third.username}.issubset(usernames)

    self_chat = client.post(
        "/api/friends-chat/",
        data=json.dumps({"username": user.username}),
        content_type="application/json",
    )
    assert self_chat.status_code == 400
    assert self_chat.json()["error"] == "You cannot chat with yourself."

    missing_user = client.post(
        "/api/friends-chat/",
        data=json.dumps({"username": "missing_diner"}),
        content_type="application/json",
    )
    assert missing_user.status_code == 404
    assert "not found" in missing_user.json()["error"].lower()

    created = client.post(
        "/api/friends-chat/",
        data=json.dumps({"username": third.username}),
        content_type="application/json",
    )
    assert created.status_code == 201
    assert created.json()["conversation"]["id"]

    # Existing one-on-one conversation should be re-used.
    reused = client.post(
        "/api/friends-chat/",
        data=json.dumps({"username": other.username}),
        content_type="application/json",
    )
    assert reused.status_code == 201
    assert reused.json()["conversation"]["id"] == convo.id


def test_friends_chat_detail_api_access_get_and_post_conditions():
    client = APIClient()
    owner = _create_user("detail_owner", role="diner")
    friend = _create_user("detail_friend", role="diner")
    outsider = _create_user("detail_outsider", role="diner")
    restaurant = Restaurant.objects.create(
        name="Shared List Spot",
        cuisine_type="other",
        price_range="$$",
    )
    convo = FriendConversation.objects.create(user1=owner, user2=friend, is_group=False)
    convo.participants.add(owner, friend)
    unread = FriendMessage.objects.create(
        conversation=convo,
        sender=friend,
        body="unread message",
        is_read=False,
    )
    FriendSharedRestaurant.objects.create(
        conversation=convo,
        restaurant=restaurant,
        added_by=owner,
    )

    client.force_login(outsider)
    denied = client.get(f"/api/friends-chat/{convo.id}/")
    assert denied.status_code == 403
    assert denied.json()["error"] == "Access denied."

    client.force_login(owner)
    get_ok = client.get(f"/api/friends-chat/{convo.id}/")
    assert get_ok.status_code == 200
    get_payload = get_ok.json()
    assert get_payload["messages"]
    assert get_payload["shared_restaurants"]
    unread.refresh_from_db()
    assert unread.is_read is True

    empty_body = client.post(
        f"/api/friends-chat/{convo.id}/",
        data=json.dumps({"body": "   "}),
        content_type="application/json",
    )
    assert empty_body.status_code == 400
    assert empty_body.json()["error"] == "Message body is required."

    sent = client.post(
        f"/api/friends-chat/{convo.id}/",
        data=json.dumps({"body": "new message"}),
        content_type="application/json",
    )
    assert sent.status_code == 201
    assert sent.json()["message"]["body"] == "new message"
