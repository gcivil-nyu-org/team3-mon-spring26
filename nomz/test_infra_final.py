"""
Infra tests: SystemMonitoringMiddleware (nomz.middleware) and recommendation
learning helpers in nomz.signals.

Note on line targets:
- ``nomz.middleware`` 170–192 / 204–229 / 244–289 are admin-write auditing,
  unhandled-exception auditing, and health-check failure auditing + alerts.
  They are not Django session expiry or CSRF token checks; those live in
  Django's own middleware.
- ``nomz.signals`` 201–269 are inside ``_adjust_weights_for_better_accuracy``
  (preference weight tuning). There is no ``m2m_changed`` receiver in this
  app; coverage is driven by ``recalculate_user_recommendation_model`` with
  enough interaction history and mixed ``RecalculatedRecommendation`` rows.
"""

import uuid
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from nomz.middleware import SystemMonitoringMiddleware
from django.db.models.signals import m2m_changed

from nomz.models import (
    FriendConversation,
    RecalculatedRecommendation,
    Restaurant,
    SystemAlert,
    SystemAuditLog,
    UserInteractionHistory,
    UserPreference,
)
from nomz.signals import recalculate_user_recommendation_model


@pytest.mark.django_db
def test_middleware_admin_get_skips_admin_write_audit():
    """Covers middleware ~168–169: mutating methods only."""
    staff = User.objects.create_user(
        username=f"staffg_{uuid.uuid4().hex[:8]}",
        password="x",
        is_staff=True,
    )

    def get_response(_request):
        return HttpResponse("ok")

    mw = SystemMonitoringMiddleware(get_response)
    rf = RequestFactory()
    request = rf.get("/admin/")
    request.user = staff

    t0 = timezone.now()
    mw(request)

    assert not SystemAuditLog.objects.filter(
        action="admin_write",
        created_at__gte=t0,
    ).exists()


@pytest.mark.django_db
def test_middleware_non_staff_post_admin_skips_admin_write_audit():
    """Covers middleware ~170–176: only staff accounts are audited for admin writes."""
    pleb = User.objects.create_user(
        username=f"pleb_{uuid.uuid4().hex[:8]}",
        password="x",
        is_staff=False,
    )

    def get_response(_request):
        return HttpResponse("ok")

    mw = SystemMonitoringMiddleware(get_response)
    rf = RequestFactory()
    request = rf.post("/admin/login/")
    request.user = pleb

    t0 = timezone.now()
    mw(request)

    assert not SystemAuditLog.objects.filter(
        action="admin_write",
        created_at__gte=t0,
    ).exists()


@pytest.mark.django_db
def test_middleware_health_200_skips_health_failure_handler():
    """Covers middleware ~241–242: healthy response does not open health-failure branch."""

    def healthy(_request):
        return HttpResponse("ok", status=200)

    mw = SystemMonitoringMiddleware(healthy)
    rf = RequestFactory()
    request = rf.get("/health/")
    request.user = AnonymousUser()

    t0 = timezone.now()
    mw(request)

    assert not SystemAuditLog.objects.filter(
        action="health_check_failure",
        created_at__gte=t0,
    ).exists()


@pytest.mark.django_db
def test_middleware_staff_post_admin_write_audit_log():
    """Hits middleware ~170–192: staff POST under /admin/ → ``admin_write`` audit."""
    staff = User.objects.create_user(
        username=f"staff_{uuid.uuid4().hex[:8]}",
        password="x",
        is_staff=True,
    )

    def get_response(_request):
        return HttpResponse("ok", status=200)

    mw = SystemMonitoringMiddleware(get_response)
    rf = RequestFactory()
    request = rf.post("/admin/auth/user/add/")
    request.user = staff
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    request.META["HTTP_USER_AGENT"] = "pytest-admin"

    t0 = timezone.now()
    mw(request)

    assert SystemAuditLog.objects.filter(
        action="admin_write",
        actor_user=staff,
        http_method="POST",
        created_at__gte=t0,
    ).exists()


@pytest.mark.django_db
def test_middleware_unhandled_exception_audit_log():
    """Hits middleware ~204–229: view raises → ``unhandled_exception`` audit."""

    def boom(_request):
        raise ValueError("simulated view failure")

    mw = SystemMonitoringMiddleware(boom)
    rf = RequestFactory()
    request = rf.get("/some/api/endpoint/")
    request.user = AnonymousUser()
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    request.META["HTTP_USER_AGENT"] = "pytest"

    t0 = timezone.now()
    with pytest.raises(ValueError, match="simulated view failure"):
        mw(request)

    log = SystemAuditLog.objects.filter(
        action="unhandled_exception",
        created_at__gte=t0,
    ).first()
    assert log is not None
    assert log.metadata.get("exception_class") == "ValueError"
    assert "simulated view failure" in (log.metadata.get("exception_message") or "")


@pytest.mark.django_db
def test_middleware_health_check_non_200_audit_and_alert_deduped():
    """Hits middleware ~244–289: failing ``/health`` response → audit + one alert per bucket."""

    def unhealthy(_request):
        return HttpResponse("unhealthy", status=503)

    mw = SystemMonitoringMiddleware(unhealthy)
    rf = RequestFactory()
    request = rf.get("/health/")
    request.user = AnonymousUser()
    request.META["REMOTE_ADDR"] = "127.0.0.1"

    t0 = timezone.now()
    mw(request)
    mw(request)

    audits = SystemAuditLog.objects.filter(
        action="health_check_failure",
        created_at__gte=t0,
    )
    assert audits.count() == 2

    alerts = SystemAlert.objects.filter(
        alert_type="HEALTH_CHECK_FAILURE",
        created_at__gte=t0,
    )
    assert alerts.count() == 1


@pytest.mark.django_db
def test_signals_recalculate_triggers_weight_adjustment_block():
    """Hits signals ``_adjust_weights_for_better_accuracy`` (~201–269) via ``recalculate_user_recommendation_model``."""
    suffix = uuid.uuid4().hex[:8]
    user = User.objects.create_user(username=f"diner_{suffix}", password="x")
    prefs = UserPreference.objects.create(user=user)

    for _ in range(3):
        UserInteractionHistory.objects.create(
            user=user,
            restaurant=None,
            interaction_type="view",
        )

    def _rest(name_suffix: str) -> Restaurant:
        return Restaurant.objects.create(
            name=f"RInfra_{name_suffix}_{suffix}",
            owner=None,
        )

    r_ok = _rest("ok")
    r_miss = [_rest(f"m{i}") for i in range(3)]

    RecalculatedRecommendation.objects.create(
        user=user,
        restaurant=r_ok,
        recommendation_score=Decimal("70.00"),
        cuisine_score=Decimal("9.00"),
        price_score=Decimal("2.00"),
        dietary_score=Decimal("9.00"),
        user_interacted=True,
    )
    for r in r_miss:
        RecalculatedRecommendation.objects.create(
            user=user,
            restaurant=r,
            recommendation_score=Decimal("60.00"),
            cuisine_score=Decimal("1.00"),
            price_score=Decimal("9.00"),
            dietary_score=Decimal("1.00"),
            user_interacted=False,
        )

    cuisine_before = prefs.cuisine_weight
    price_before = prefs.price_weight
    dietary_before = prefs.dietary_weight
    version_before = prefs.recommendation_model_version

    recalculate_user_recommendation_model(user.id)

    prefs.refresh_from_db()
    assert prefs.recommendation_model_version == version_before + 1
    assert prefs.cuisine_weight > cuisine_before
    assert prefs.price_weight < price_before
    assert prefs.dietary_weight > dietary_before
    assert prefs.last_weights_adjustment_reason
    assert "Adjusted weights" in prefs.last_weights_adjustment_reason


@pytest.mark.django_db
def test_signals_recalculate_exits_adjust_weights_when_no_successful_recs():
    """Covers signals ~204–205: learning sees poor rate but no successful rows to learn from."""
    suffix = uuid.uuid4().hex[:8]
    user = User.objects.create_user(username=f"diner0_{suffix}", password="x")
    prefs = UserPreference.objects.create(user=user)

    for _ in range(3):
        UserInteractionHistory.objects.create(
            user=user,
            restaurant=None,
            interaction_type="menu_viewed",
        )

    for i in range(4):
        r = Restaurant.objects.create(
            name=f"RAllMiss_{i}_{suffix}",
            owner=None,
        )
        RecalculatedRecommendation.objects.create(
            user=user,
            restaurant=r,
            recommendation_score=Decimal("55.00"),
            cuisine_score=Decimal("5.00"),
            price_score=Decimal("5.00"),
            dietary_score=Decimal("5.00"),
            user_interacted=False,
        )

    version_before = prefs.recommendation_model_version
    recalculate_user_recommendation_model(user.id)
    prefs.refresh_from_db()
    assert prefs.recommendation_model_version == version_before + 1
    assert not prefs.last_weights_adjustment_reason


@pytest.mark.django_db
def test_signals_recalculate_triggers_weight_decrease_branches():
    """Covers the ``else`` weight branches in ``_adjust_weights_for_better_accuracy`` (~241–264)."""
    suffix = uuid.uuid4().hex[:8]
    user = User.objects.create_user(username=f"diner2_{suffix}", password="x")
    prefs = UserPreference.objects.create(user=user)

    for _ in range(3):
        UserInteractionHistory.objects.create(
            user=user,
            restaurant=None,
            interaction_type="search",
        )

    def _rest(name_suffix: str) -> Restaurant:
        return Restaurant.objects.create(
            name=f"RInfra2_{name_suffix}_{suffix}",
            owner=None,
        )

    r_ok = _rest("ok")
    r_miss = [_rest(f"m{i}") for i in range(3)]

    RecalculatedRecommendation.objects.create(
        user=user,
        restaurant=r_ok,
        recommendation_score=Decimal("70.00"),
        cuisine_score=Decimal("1.00"),
        price_score=Decimal("9.00"),
        dietary_score=Decimal("1.00"),
        user_interacted=True,
    )
    for r in r_miss:
        RecalculatedRecommendation.objects.create(
            user=user,
            restaurant=r,
            recommendation_score=Decimal("60.00"),
            cuisine_score=Decimal("9.00"),
            price_score=Decimal("1.00"),
            dietary_score=Decimal("9.00"),
            user_interacted=False,
        )

    cuisine_before = prefs.cuisine_weight
    price_before = prefs.price_weight
    dietary_before = prefs.dietary_weight

    recalculate_user_recommendation_model(user.id)

    prefs.refresh_from_db()
    assert prefs.cuisine_weight < cuisine_before
    assert prefs.price_weight > price_before
    assert prefs.dietary_weight < dietary_before


@pytest.mark.django_db
def test_friend_conversation_participants_m2m_add_remove_fires_signal():
    """Exercise ``m2m_changed`` on friend-chat participants (no handler in ``nomz.signals``)."""
    suffix = uuid.uuid4().hex[:8]
    u1 = User.objects.create_user(username=f"fc1_{suffix}", password="x")
    u2 = User.objects.create_user(username=f"fc2_{suffix}", password="x")
    fc = FriendConversation.objects.create(is_group=True, name=f"g_{suffix}")

    seen: list[str] = []

    def _capture(sender, action, **kwargs):
        seen.append(action)

    through = FriendConversation.participants.through
    m2m_changed.connect(_capture, sender=through)
    try:
        fc.participants.add(u1, u2)
        fc.participants.remove(u1)
    finally:
        m2m_changed.disconnect(_capture, sender=through)

    assert "post_add" in seen
    assert "pre_remove" in seen or "post_remove" in seen
    assert set(fc.participants.all()) == {u2}
