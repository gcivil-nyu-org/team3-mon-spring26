"""
Smoke GET for every named route in `nomz.urls`, Django `Client` tests for wired
`nomz.views` endpoints, `RequestFactory` for legacy HTML views not mounted in
`nomz.urls` (they share SPA shell routes), and direct `Form` validation tests for
`nomz.forms`.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import NoReverseMatch, URLPattern, reverse
from PIL import Image

from nomz import urls as nomz_urls
from nomz import views as nomz_views
from nomz.forms import (
    AdminLoginForm,
    ModerationReportForm,
    RestaurantActivationForm,
    RestaurantAvailabilityForm,
    RestaurantCommunicationSettingsForm,
    RestaurantOwnershipClaimForm,
    RestaurantPhotoForm,
    RestaurantProfileForm,
    ReviewForm,
    ReviewResponseForm,
    UserLoginForm,
    UserPreferenceForm,
    UserRegisterForm,
)
from nomz.models import (
    CompositeScoreAnomaly,
    CompositeScoreHistory,
    Conversation,
    FriendConversation,
    FriendSharedRestaurant,
    InspectionRecord,
    ModerationReport,
    Restaurant,
    RestaurantOwnershipClaim,
    Review,
    ReviewResponse,
    UserPreference,
    UserProfile,
)

pytestmark = pytest.mark.django_db


def _uid() -> str:
    return uuid.uuid4().hex[:10]


def _named_url_patterns():
    for p in nomz_urls.urlpatterns:
        if isinstance(p, URLPattern) and p.name:
            yield p


def _default_kwargs_for_pattern(pattern: URLPattern) -> dict:
    converters = getattr(pattern.pattern, "converters", {}) or {}
    kwargs: dict = {}
    for key in converters:
        if key in (
            "restaurant_id",
            "conversation_id",
            "user_id",
            "report_id",
            "photo_id",
            "content_id",
            "anomaly_id",
        ):
            kwargs[key] = 1
        elif key == "asset_path":
            kwargs[key] = "index.html"
        elif key == "username":
            kwargs[key] = "routeuser"
        elif key == "content_type":
            kwargs[key] = "review"
        elif key == "uidb64":
            kwargs[key] = "MQ"
        elif key == "token":
            kwargs[key] = "token-placeholder"
        else:
            kwargs[key] = 1
    return kwargs


def _collect_named_routes():
    return [(p.name, _default_kwargs_for_pattern(p)) for p in _named_url_patterns()]


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def staff_user(db):
    u = User.objects.create_user(
        username=f"staff_{_uid()}",
        email=f"{_uid()}@s.com",
        password="Str0ngPass!x",
        is_staff=True,
    )
    UserProfile.objects.create(user=u, role="diner", is_approved=True)
    return u


@pytest.fixture
def diner_user(db):
    u = User.objects.create_user(
        username=f"diner_{_uid()}",
        email=f"{_uid()}@d.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=u, role="diner", is_approved=True)
    return u


@pytest.fixture
def owner_user(db):
    u = User.objects.create_user(
        username=f"owner_{_uid()}",
        email=f"{_uid()}@o.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=u, role="restaurant", is_approved=True)
    r = Restaurant.objects.create(
        owner=u,
        name=f"Owned_{_uid()}",
        cuisine_type="italian",
        price_range="$$",
        is_active=True,
        messaging_enabled=True,
    )
    return u, r


# ---------------------------------------------------------------------------
# GET every named URL in nomz.urls (smoke: no 5xx)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,kwargs", _collect_named_routes())
def test_nomz_named_route_get_smoke(client, staff_user, name, kwargs):
    """
    Every named `nomz.urls` pattern is reachable via GET without server errors.
    Many routes return 302 (auth), 403/401 (API), or 405 (POST-only JSON).
    """
    try:
        url = reverse(name, kwargs=kwargs)
    except NoReverseMatch:
        pytest.skip(f"reverse missing optional app: {name}")
    client.force_login(staff_user)
    resp = client.get(url, follow=False)
    assert resp.status_code < 500, f"{name} {kwargs} -> {resp.status_code}"


# ---------------------------------------------------------------------------
# views.py — wired URLs (Django Client)
# ---------------------------------------------------------------------------


def test_health_check_get_json(client):
    r = client.get(reverse("health_check"))
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


@patch("nomz.views.refresh_restaurant_composite", return_value={"anomaly_count": 0})
def test_admin_recalculate_scores_post_success(
    _mock_refresh, client, staff_user, owner_user
):
    _o, rest = owner_user
    client.force_login(staff_user)
    r = client.post(
        reverse("admin_recalculate_scores"),
        {"restaurant_id": str(rest.id)},
        follow=False,
    )
    assert r.status_code == 302


def test_admin_recalculate_scores_invalid_id_redirects(client, staff_user):
    client.force_login(staff_user)
    r = client.post(
        reverse("admin_recalculate_scores"),
        {"restaurant_id": "not-a-number"},
        follow=False,
    )
    assert r.status_code == 302


def test_admin_recalculate_scores_multiple_partial_name_redirects(client, staff_user):
    tag = _uid()
    Restaurant.objects.create(
        owner=None,
        name=f"Foo Bar Alpha {tag}",
        cuisine_type="italian",
        price_range="$$",
        is_active=True,
    )
    Restaurant.objects.create(
        owner=None,
        name=f"Foo Bar Beta {tag}",
        cuisine_type="mexican",
        price_range="$",
        is_active=True,
    )
    client.force_login(staff_user)
    r = client.post(
        reverse("admin_recalculate_scores"),
        {"restaurant_name": f"Foo Bar {tag}"},
        follow=False,
    )
    assert r.status_code == 302


@patch("nomz.views.refresh_restaurant_composite", return_value={"anomaly_count": 0})
def test_admin_recalculate_scores_name_no_match(_mock_refresh, client, staff_user):
    client.force_login(staff_user)
    r = client.post(
        reverse("admin_recalculate_scores"),
        {"restaurant_name": f"nonexistent_{_uid()}"},
        follow=False,
    )
    assert r.status_code == 302


@patch("nomz.views.refresh_restaurant_composite", return_value={"anomaly_count": 0})
def test_admin_recalculate_scores_empty_queryset(_mock_refresh, client, staff_user):
    client.force_login(staff_user)
    r = client.post(
        reverse("admin_recalculate_scores"),
        {"restaurant_id": "999999999"},
        follow=False,
    )
    assert r.status_code == 302


def test_admin_resolve_score_anomaly_post(client, staff_user, owner_user):
    _o, rest = owner_user
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
    client.force_login(staff_user)
    r = client.post(
        reverse("admin_resolve_score_anomaly", kwargs={"anomaly_id": an.id}),
        follow=False,
    )
    assert r.status_code == 302


def test_admin_resolve_score_anomaly_already_resolved(client, staff_user, owner_user):
    _o, rest = owner_user
    hist = CompositeScoreHistory.objects.create(
        restaurant=rest,
        trigger_source=CompositeScoreHistory.TRIGGER_ADMIN_DASHBOARD,
    )
    an = CompositeScoreAnomaly.objects.create(
        restaurant=rest,
        score_history=hist,
        anomaly_type=CompositeScoreAnomaly.TYPE_LARGE_DELTA,
        severity=CompositeScoreAnomaly.SEVERITY_HIGH,
        is_resolved=True,
    )
    client.force_login(staff_user)
    r = client.post(
        reverse("admin_resolve_score_anomaly", kwargs={"anomaly_id": an.id}),
        follow=False,
    )
    assert r.status_code == 302


def test_respond_to_review_post_valid_next_redirect(client, owner_user, diner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="Great",
    )
    client.force_login(owner)
    r = client.post(
        reverse("respond_to_review", kwargs={"review_id": rev.id}),
        {"response_text": "Thanks!", "next": "/search/"},
        follow=False,
    )
    assert r.status_code == 302
    assert r["Location"].endswith("/search/")


def test_respond_to_review_post_valid(client, owner_user, diner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="Great",
    )
    client.force_login(owner)
    r = client.post(
        reverse("respond_to_review", kwargs={"review_id": rev.id}),
        {"response_text": "Thank you for dining with us!"},
        follow=False,
    )
    assert r.status_code == 302
    assert ReviewResponse.objects.filter(review=rev).exists()


def test_respond_to_review_post_invalid_form(client, owner_user, diner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=4,
        comment="ok",
    )
    client.force_login(owner)
    r = client.post(
        reverse("respond_to_review", kwargs={"review_id": rev.id}),
        {"response_text": ""},
        follow=False,
    )
    assert r.status_code == 302
    assert not ReviewResponse.objects.filter(review=rev).exists()


def test_respond_to_review_forbidden_non_owner(client, owner_user, diner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=3,
        comment="x",
    )
    client.force_login(diner_user)
    r = client.post(
        reverse("respond_to_review", kwargs={"review_id": rev.id}),
        {"response_text": "Hijack"},
        follow=False,
    )
    assert r.status_code == 403


def test_respond_to_review_deleted_review_redirects(client, owner_user, diner_user):
    owner, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=2,
        comment="gone",
        is_deleted=True,
    )
    client.force_login(owner)
    r = client.post(
        reverse("respond_to_review", kwargs={"review_id": rev.id}),
        {"response_text": "Too late"},
        follow=False,
    )
    assert r.status_code == 302


# ---------------------------------------------------------------------------
# views.py — RequestFactory (not mounted as view callables in nomz.urls)
# ---------------------------------------------------------------------------


def _attach_session_and_messages(request):
    """RequestFactory requests need session + messages storage for views using `messages`."""
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    request.session.save()
    MessageMiddleware(lambda r: HttpResponse()).process_request(request)


def _rf_post(user, path, data):
    rf = RequestFactory()
    req = rf.post(path, data=data)
    req.user = user
    _attach_session_and_messages(req)
    return req


def _rf_get(user, path):
    rf = RequestFactory()
    req = rf.get(path)
    req.user = user
    _attach_session_and_messages(req)
    return req


def test_user_logout_post_rf(diner_user):
    req = _rf_post(diner_user, "/logout/", {})
    resp = nomz_views.user_logout(req)
    assert resp.status_code == 302


def test_admin_toggle_user_status_post_rf(staff_user, diner_user):
    req = _rf_post(
        staff_user,
        f"/nomz-admin/users/{diner_user.id}/toggle/",
        {"action": "deactivate"},
    )
    resp = nomz_views.admin_toggle_user_status(req, diner_user.id)
    assert resp.status_code == 302


def test_admin_toggle_user_status_self_error_rf(staff_user):
    req = _rf_post(
        staff_user,
        f"/nomz-admin/users/{staff_user.id}/toggle/",
        {"action": "deactivate"},
    )
    resp = nomz_views.admin_toggle_user_status(req, staff_user.id)
    assert resp.status_code == 302


def test_admin_resolve_report_dismiss_rf(staff_user, diner_user, owner_user):
    _o, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=3,
        comment="spam",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="SPAM",
        details="x",
        status="PENDING",
    )
    req = _rf_post(
        staff_user,
        f"/nomz-admin/moderation/resolve/{rep.id}/",
        {"action": "dismiss", "moderator_note": "ok"},
    )
    resp = nomz_views.admin_resolve_report(req, rep.id)
    assert resp.status_code == 302


def test_admin_resolve_report_flag_fraud_user_rf(staff_user, diner_user, owner_user):
    owner, _rest = owner_user
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        reported_user=owner,
        review=None,
        reason="FRAUD",
        details="bad actor",
        status="PENDING",
    )
    req = _rf_post(
        staff_user,
        f"/nomz-admin/moderation/resolve/{rep.id}/",
        {"action": "flag_fraud", "moderator_note": "flagged"},
    )
    resp = nomz_views.admin_resolve_report(req, rep.id)
    assert resp.status_code == 302


def test_message_restaurant_redirects_to_conversation(diner_user, owner_user):
    _owner, rest = owner_user
    req = _rf_get(diner_user, f"/messages/restaurant/{rest.id}/")
    resp = nomz_views.message_restaurant(req, rest.id)
    assert resp.status_code == 302
    assert Conversation.objects.filter(restaurant=rest, diner=diner_user).exists()


def test_message_restaurant_owner_forbidden(owner_user):
    owner, rest = owner_user
    req = _rf_get(owner, f"/messages/restaurant/{rest.id}/")
    resp = nomz_views.message_restaurant(req, rest.id)
    assert resp.status_code == 302


def test_create_group_chat_post(diner_user):
    buddy = User.objects.create_user(
        username=f"buddy_{_uid()}",
        email=f"{_uid()}@b.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    req = _rf_post(
        diner_user,
        "/friends-chat/group/create/",
        {"group_name": "Lunch Crew", "participants": [str(buddy.id)]},
    )
    resp = nomz_views.create_group_chat(req)
    assert resp.status_code == 302


def test_create_group_chat_missing_name_redirects(diner_user):
    req = _rf_post(diner_user, "/friends-chat/group/create/", {"group_name": ""})
    resp = nomz_views.create_group_chat(req)
    assert resp.status_code == 302


def test_manage_group_member_resolve_by_username(diner_user):
    buddy = User.objects.create_user(
        username=f"uname_{_uid()}",
        email=f"{_uid()}@u.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(
        name="ByName", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "username": buddy.username},
    )
    assert nomz_views.manage_group_member(req, conv.id).status_code == 302


def test_manage_group_member_add_remove(diner_user):
    buddy = User.objects.create_user(
        username=f"mate_{_uid()}",
        email=f"{_uid()}@m.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(
        name="G", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "user_id": str(buddy.id)},
    )
    assert nomz_views.manage_group_member(req, conv.id).status_code == 302
    req2 = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/manage/",
        {"action": "remove", "user_id": str(buddy.id)},
    )
    assert nomz_views.manage_group_member(req2, conv.id).status_code == 302


def test_leave_group_member(diner_user):
    leader = User.objects.create_user(
        username=f"lead_{_uid()}",
        email=f"{_uid()}@l.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=leader, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(name="Team", is_group=True, creator=leader)
    conv.participants.add(leader, diner_user)
    req = _rf_post(diner_user, f"/friends-chat/group/{conv.id}/leave/", {})
    assert nomz_views.leave_group(req, conv.id).status_code == 302


def test_recommend_friend_restaurant_by_username(diner_user, owner_user):
    _o, rest = owner_user
    buddy = User.objects.create_user(
        username=f"pal_{_uid()}",
        email=f"{_uid()}@p.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    u1, u2 = (diner_user, buddy) if diner_user.id < buddy.id else (buddy, diner_user)
    FriendConversation.objects.create(user1=u1, user2=u2, is_group=False)
    req = _rf_post(
        diner_user,
        f"/friends-chat/{buddy.username}/recommend/",
        {"restaurant_id": str(rest.id), "body": "Try this"},
    )
    resp = nomz_views.recommend_friend_restaurant(req, username=buddy.username)
    assert resp.status_code == 302


def test_message_restaurant_no_owner(diner_user, db):
    r = Restaurant.objects.create(
        owner=None,
        name=f"NoOwner_{_uid()}",
        cuisine_type="italian",
        price_range="$$",
        is_active=True,
        messaging_enabled=True,
    )
    req = _rf_get(diner_user, f"/messages/restaurant/{r.id}/")
    resp = nomz_views.message_restaurant(req, r.id)
    assert resp.status_code == 302


def test_message_restaurant_messaging_disabled(diner_user, owner_user):
    owner, rest = owner_user
    rest.messaging_enabled = False
    rest.save(update_fields=["messaging_enabled"])
    req = _rf_get(diner_user, f"/messages/restaurant/{rest.id}/")
    resp = nomz_views.message_restaurant(req, rest.id)
    assert resp.status_code == 302


def test_admin_resolve_report_unflag_and_delete_rf(staff_user, diner_user, owner_user):
    _o, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=3,
        comment="x",
        is_flagged=True,
    )
    rep1 = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="u",
        status="PENDING",
    )
    req1 = _rf_post(
        staff_user,
        f"/nomz-admin/moderation/resolve/{rep1.id}/",
        {"action": "unflag", "moderator_note": ""},
    )
    assert nomz_views.admin_resolve_report(req1, rep1.id).status_code == 302

    rep2 = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="del",
        status="PENDING",
    )
    req2 = _rf_post(
        staff_user,
        f"/nomz-admin/moderation/resolve/{rep2.id}/",
        {"action": "delete", "moderator_note": "gone"},
    )
    assert nomz_views.admin_resolve_report(req2, rep2.id).status_code == 302
    rev.refresh_from_db()
    assert rev.is_deleted is True


def test_admin_resolve_report_reevaluate_rf(staff_user, diner_user, owner_user):
    _o, rest = owner_user
    rev = Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=5,
        comment="z",
    )
    rep = ModerationReport.objects.create(
        reporter=diner_user,
        review=rev,
        reason="OTHER",
        details="re",
        status="RESOLVED",
    )
    req = _rf_post(
        staff_user,
        f"/nomz-admin/moderation/resolve/{rep.id}/",
        {"action": "reevaluate", "moderator_note": "again"},
    )
    assert nomz_views.admin_resolve_report(req, rep.id).status_code == 302


def test_create_group_chat_get_redirects(diner_user):
    rf = RequestFactory()
    req = rf.get("/friends-chat/group/create/")
    req.user = diner_user
    _attach_session_and_messages(req)
    assert nomz_views.create_group_chat(req).status_code == 302


def test_manage_group_member_forbidden_non_creator(diner_user):
    other = User.objects.create_user(
        username=f"adm_{_uid()}",
        email=f"{_uid()}@a.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=other, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(
        name="NotMine", is_group=True, creator=other
    )
    conv.participants.add(other, diner_user)
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "user_id": str(diner_user.id)},
    )
    assert nomz_views.manage_group_member(req, conv.id).status_code == 302


def test_manage_group_member_add_non_diner_error(diner_user, owner_user):
    owner, _rest = owner_user
    conv = FriendConversation.objects.create(
        name="G2", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/manage/",
        {"action": "add", "user_id": str(owner.id)},
    )
    assert nomz_views.manage_group_member(req, conv.id).status_code == 302


def test_manage_group_member_remove_creator_error(diner_user):
    conv = FriendConversation.objects.create(
        name="G3", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/manage/",
        {"action": "remove", "user_id": str(diner_user.id)},
    )
    assert nomz_views.manage_group_member(req, conv.id).status_code == 302


def test_leave_group_creator_blocked(diner_user):
    conv = FriendConversation.objects.create(
        name="Solo", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user)
    req = _rf_post(diner_user, f"/friends-chat/group/{conv.id}/leave/", {})
    assert nomz_views.leave_group(req, conv.id).status_code == 302


def test_leave_group_no_access_redirects(diner_user):
    other = User.objects.create_user(
        username=f"out_{_uid()}",
        email=f"{_uid()}@o.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=other, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(
        name="Private", is_group=True, creator=other
    )
    conv.participants.add(other)
    req = _rf_post(diner_user, f"/friends-chat/group/{conv.id}/leave/", {})
    assert nomz_views.leave_group(req, conv.id).status_code == 302


def test_recommend_friend_post_by_restaurant_name(diner_user, owner_user):
    _o, rest = owner_user
    buddy = User.objects.create_user(
        username=f"rn_{_uid()}",
        email=f"{_uid()}@rn.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    u1, u2 = (diner_user, buddy) if diner_user.id < buddy.id else (buddy, diner_user)
    FriendConversation.objects.create(user1=u1, user2=u2, is_group=False)
    req = _rf_post(
        diner_user,
        f"/friends-chat/{buddy.username}/recommend/",
        {"restaurant_name": rest.name, "body": "via name"},
    )
    assert (
        nomz_views.recommend_friend_restaurant(req, username=buddy.username).status_code
        == 302
    )


def test_recommend_friend_get_only_redirects(diner_user):
    buddy = User.objects.create_user(
        username=f"bg_{_uid()}",
        email=f"{_uid()}@b.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    u1, u2 = (diner_user, buddy) if diner_user.id < buddy.id else (buddy, diner_user)
    FriendConversation.objects.create(user1=u1, user2=u2, is_group=False)
    rf = RequestFactory()
    req = rf.get(f"/friends-chat/{buddy.username}/recommend/")
    req.user = diner_user
    _attach_session_and_messages(req)
    resp = nomz_views.recommend_friend_restaurant(req, username=buddy.username)
    assert resp.status_code == 302


def test_toggle_shared_add_by_restaurant_name(diner_user, owner_user):
    _o, rest = owner_user
    buddy = User.objects.create_user(
        username=f"tsn_{_uid()}",
        email=f"{_uid()}@ts.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(
        name="TSN", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user, buddy)
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/toggle-shared/",
        {"restaurant_name": rest.name, "action": "add"},
    )
    assert (
        nomz_views.toggle_shared_restaurant(
            req, username=None, conversation_id=conv.id
        ).status_code
        == 302
    )


def test_toggle_shared_remove(diner_user, owner_user):
    _o, rest = owner_user
    buddy = User.objects.create_user(
        username=f"p3_{_uid()}",
        email=f"{_uid()}@p3.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(
        name="Tog", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user, buddy)
    FriendSharedRestaurant.objects.create(
        conversation=conv, restaurant=rest, added_by=diner_user
    )
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/toggle-shared/",
        {"restaurant_id": str(rest.id), "action": "remove"},
    )
    resp = nomz_views.toggle_shared_restaurant(
        req, username=None, conversation_id=conv.id
    )
    assert resp.status_code == 302
    assert not FriendSharedRestaurant.objects.filter(
        conversation=conv, restaurant=rest
    ).exists()


def test_toggle_shared_restaurant_group_id(diner_user, owner_user):
    _o, rest = owner_user
    buddy = User.objects.create_user(
        username=f"p2_{_uid()}",
        email=f"{_uid()}@p2.com",
        password="Str0ngPass!x",
    )
    UserProfile.objects.create(user=buddy, role="diner", is_approved=True)
    conv = FriendConversation.objects.create(
        name="Share", is_group=True, creator=diner_user
    )
    conv.participants.add(diner_user, buddy)
    req = _rf_post(
        diner_user,
        f"/friends-chat/group/{conv.id}/toggle-shared/",
        {"restaurant_id": str(rest.id), "action": "add"},
    )
    resp = nomz_views.toggle_shared_restaurant(
        req, username=None, conversation_id=conv.id
    )
    assert resp.status_code == 302
    assert FriendSharedRestaurant.objects.filter(
        conversation=conv, restaurant=rest
    ).exists()


@patch(
    "nomz.views.compute_restaurant_composite_score",
    return_value={
        "composite_score": 80.0,
        "grade": "A",
        "grade_score": 90,
        "last_inspection_date": None,
        "review_count": 0,
        "review_confidence": 0.5,
        "review_factor_averages": {},
        "review_factor_scores": {},
        "score_breakdown": [],
    },
)
@patch("nomz.views.refresh_restaurant_composite", return_value={})
def test_build_restaurant_score_insights_helper(_mock_r, _mock_c, owner_user):
    _o, rest = owner_user
    rest.neighborhood = "SoHo"
    rest.composite_score = 80
    rest.grade_score_latest = 90
    rest.grade_latest = "A"
    rest.save()
    InspectionRecord.objects.create(
        restaurant=rest,
        inspection_key=f"k_{_uid()}",
        inspection_date="2024-01-15",
        grade="A",
        score=10,
        critical_violations=0,
        noncritical_violations=0,
        violation_count=0,
        inspection_type="Cycle",
        action="None",
        violations=[],
    )
    ctx = nomz_views._build_restaurant_score_insights(rest)
    assert "score_summary" in ctx
    assert ctx["trend_summary"]["has_data"] is True


# ---------------------------------------------------------------------------
# forms.py — is_valid() + errors
# ---------------------------------------------------------------------------


def test_user_register_form_valid_and_invalid():
    data_ok = {
        "email": f"{_uid()}@new.com",
        "username": f"u_{_uid()}",
        "role": "diner",
        "password1": "Str0ngPass!xyz",
        "password2": "Str0ngPass!xyz",
    }
    f = UserRegisterForm(data_ok)
    assert f.is_valid(), f.errors

    f2 = UserRegisterForm(
        {
            "email": "bad",
            "username": "",
            "role": "diner",
            "password1": "x",
            "password2": "y",
        }
    )
    assert not f2.is_valid()
    assert f2.errors


def test_user_register_form_clean_email_duplicate(diner_user):
    f = UserRegisterForm(
        {
            "email": diner_user.email,
            "username": f"other_{_uid()}",
            "role": "diner",
            "password1": "Str0ngPass!xyz",
            "password2": "Str0ngPass!xyz",
        }
    )
    assert not f.is_valid()
    assert "email" in f.errors


def test_user_login_form_invalid():
    f = UserLoginForm(data={"username": "", "password": ""})
    assert not f.is_valid()


@patch("django.contrib.auth.hashers.check_password", return_value=True)
def test_admin_login_form_valid(_mock_pw):
    import os

    os.environ["ADMIN_SECURITY_CODE"] = "ADM999"
    f = AdminLoginForm(
        data={
            "username": "admin",
            "password": "any",
            "security_code": "ADM999",
        }
    )
    assert f.is_valid(), f.errors


def test_admin_login_form_bad_security_code():
    import os

    os.environ["ADMIN_SECURITY_CODE"] = "ADM999"
    with patch("django.contrib.auth.hashers.check_password", return_value=True):
        f = AdminLoginForm(
            data={
                "username": "admin",
                "password": "any",
                "security_code": "WRONG",
            }
        )
        assert not f.is_valid()


def test_restaurant_profile_form_valid(owner_user):
    _o, rest = owner_user
    data = {
        "name": rest.name,
        "description": "Nice place",
        "cuisine_type": "italian",
        "price_range": "$$",
        "hours_open": "09:00",
        "hours_close": "22:00",
        "address": "1 Broadway",
        "phone": "555-010-0000",
        "website": "https://example.com/",
        "email": "chef@example.com",
    }
    f = RestaurantProfileForm(data=data, instance=rest)
    assert f.is_valid(), f.errors

    bad = dict(data)
    bad["website"] = "not-a-url"
    f2 = RestaurantProfileForm(data=bad, instance=rest)
    assert not f2.is_valid()


def test_restaurant_availability_form_valid_invalid(owner_user):
    _o, rest = owner_user
    f = RestaurantAvailabilityForm(
        data={
            "is_temporarily_unavailable": True,
            "unavailable_reason": "Closed",
            "unavailable_until": "",
        },
        instance=rest,
    )
    assert f.is_valid(), f.errors


def test_restaurant_activation_form(owner_user):
    _o, rest = owner_user
    f = RestaurantActivationForm(data={"is_active": False}, instance=rest)
    assert f.is_valid()


def test_restaurant_photo_form_valid(tmp_path, owner_user):
    owner, rest = owner_user
    buf = BytesIO()
    Image.new("RGB", (4, 4), color=(10, 120, 200)).save(buf, format="PNG")
    buf.seek(0)
    from django.core.files.uploadedfile import SimpleUploadedFile

    img = SimpleUploadedFile("a.png", buf.read(), content_type="image/png")
    f = RestaurantPhotoForm(
        data={"caption": "Front", "is_primary": False},
        files={"photo": img},
    )
    assert f.is_valid(), f.errors

    f2 = RestaurantPhotoForm(data={"caption": "x"}, files={})
    assert not f2.is_valid()


def test_user_preference_form_valid_invalid(diner_user):
    UserPreference.objects.create(user=diner_user)
    f = UserPreferenceForm(
        instance=diner_user.preferences,
        data={
            "favorite_cuisines": ["italian"],
            "dietary_restrictions": ["Vegan"],
            "price_preference": "$$",
            "neighborhood_preference": "SoHo",
        },
    )
    assert f.is_valid(), f.errors

    f2 = UserPreferenceForm(
        instance=diner_user.preferences,
        data={
            "favorite_cuisines": ["not-a-real-cuisine-key"],
            "dietary_restrictions": [],
            "price_preference": "$$",
            "neighborhood_preference": "",
        },
    )
    assert not f2.is_valid()


def test_restaurant_ownership_claim_form_valid(diner_user, db):
    orphan = Restaurant.objects.create(
        owner=None,
        name=f"Orphan_{_uid()}",
        cuisine_type="thai",
        price_range="$",
        is_active=True,
        address="9th Ave",
        zip_code="10001",
    )
    f = RestaurantOwnershipClaimForm(
        user=diner_user,
        data={
            "restaurant": str(orphan.id),
            "business_email": "owner@biz.com",
            "contact_phone": "555-0199",
            "proof_details": "We manage the website.",
        },
    )
    assert f.is_valid(), f.errors


def test_restaurant_ownership_claim_form_clean_errors(diner_user, owner_user):
    owner, owned = owner_user
    orphan = Restaurant.objects.create(
        owner=None,
        name=f"ClaimMe_{_uid()}",
        cuisine_type="thai",
        price_range="$",
        is_active=True,
    )
    RestaurantOwnershipClaim.objects.create(
        claimant=diner_user,
        restaurant=orphan,
        status=RestaurantOwnershipClaim.STATUS_PENDING,
    )
    f = RestaurantOwnershipClaimForm(
        user=diner_user,
        data={
            "restaurant": str(orphan.id),
            "business_email": "a@a.com",
            "contact_phone": "1",
            "proof_details": "x",
        },
    )
    assert not f.is_valid()


def test_review_form_valid_invalid(diner_user, owner_user):
    _o, rest = owner_user
    good = {
        "rating": 5,
        "food_quality_rating": 5,
        "service_quality_rating": 5,
        "ambience_rating": 5,
        "location_rating": 5,
        "value_rating": 5,
        "dietary_accommodation_rating": 5,
        "cleanliness_rating": 5,
        "comment": "Superb",
    }
    f = ReviewForm(data=good)
    assert f.is_valid(), f.errors

    bad = dict(good)
    bad["rating"] = 99
    assert not ReviewForm(data=bad).is_valid()


def test_moderation_report_form_valid_invalid(diner_user, owner_user):
    _o, rest = owner_user
    Review.objects.create(
        restaurant=rest,
        user=diner_user,
        rating=2,
        comment="bad",
    )
    f = ModerationReportForm(data={"reason": "SPAM", "details": "Promotional content"})
    assert f.is_valid(), f.errors

    assert not ModerationReportForm(data={"reason": "SPAM", "details": ""}).is_valid()


def test_review_response_form_valid_invalid():
    f = ReviewResponseForm(data={"response_text": "Thanks for visiting."})
    assert f.is_valid(), f.errors

    assert not ReviewResponseForm(data={"response_text": ""}).is_valid()


def test_restaurant_communication_settings_form_valid_invalid(owner_user):
    _o, rest = owner_user
    f = RestaurantCommunicationSettingsForm(
        data={
            "messaging_enabled": True,
            "response_hours_start": "9:00 AM",
            "response_hours_end": "5:00 PM",
        },
        instance=rest,
    )
    assert f.is_valid(), f.errors

    f2 = RestaurantCommunicationSettingsForm(
        data={
            "messaging_enabled": True,
            "response_hours_start": "6:00 PM",
            "response_hours_end": "9:00 AM",
        },
        instance=rest,
    )
    assert not f2.is_valid()
