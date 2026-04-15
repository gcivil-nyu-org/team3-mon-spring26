from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import path

from nomz.models import (
    LoginLog,
    RecalculatedRecommendation,
    Restaurant,
    Review,
    SystemAlert,
    SystemAuditLog,
    UserPreference,
    UserProfile,
)


def _admin_post_view(_request):
    return HttpResponse("ok", status=200)


def _health_fail_view(_request):
    return HttpResponse("unhealthy", status=503)


urlpatterns = [
    path("admin/test-write/", _admin_post_view, name="test_admin_post"),
    path("health/", _health_fail_view, name="test_health_fail"),
]


@override_settings(
    ROOT_URLCONF="nomz.tests_middleware_signals",
    SYSTEM_METRICS_SNAPSHOT_INTERVAL_SECONDS=600,
    SYSTEM_ALERT_ERROR_RATE_THRESHOLD=1.1,
    SYSTEM_ALERT_AVG_LATENCY_MS_THRESHOLD=100000,
)
class MiddlewareCoverageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = get_user_model().objects.create_user(
            username="mw_staff",
            password="pass12345",
            is_staff=True,
        )
        self.diner = get_user_model().objects.create_user(
            username="mw_diner",
            password="pass12345",
        )

    def test_admin_write_request_creates_audit_log_for_staff_only(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            "/admin/test-write/",
            HTTP_X_FORWARDED_FOR="203.0.113.10",
            HTTP_USER_AGENT="middleware-test-agent",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SystemAuditLog.objects.filter(
                action="admin_write",
                actor_user=self.staff,
                request_path="/admin/test-write/",
                http_method="POST",
            ).exists()
        )

        SystemAuditLog.objects.filter(action="admin_write").delete()
        self.client.force_login(self.diner)
        response = self.client.post("/admin/test-write/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SystemAuditLog.objects.filter(action="admin_write").exists())

    def test_health_failure_creates_audit_and_deduplicated_alert(self):
        self.client.force_login(self.staff)
        first = self.client.get(
            "/health/",
            HTTP_X_FORWARDED_FOR="198.51.100.2",
            HTTP_USER_AGENT="health-agent",
        )
        self.assertEqual(first.status_code, 503)

        health_audit = SystemAuditLog.objects.filter(action="health_check_failure").first()
        self.assertIsNotNone(health_audit)
        self.assertEqual(health_audit.metadata.get("status_code"), 503)
        self.assertEqual(health_audit.request_path, "/health/")

        # Second request in same bucket should not create another active alert.
        second = self.client.get("/health/")
        self.assertEqual(second.status_code, 503)
        self.assertEqual(
            SystemAlert.objects.filter(
                alert_type="HEALTH_CHECK_FAILURE",
                is_active=True,
            ).count(),
            1,
        )


class SignalsCoverageTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="signals_user",
            password="pass12345",
        )
        self.restaurant = Restaurant.objects.create(
            name="Signals Bistro",
            cuisine_type="other",
            price_range="$$",
            is_active=True,
        )
        UserProfile.objects.create(user=self.user, role="diner")

    def test_user_login_failed_signal_marks_suspicious_after_repeated_failures(self):
        LoginLog.objects.create(
            username="signals_user",
            ip_address="203.0.113.20",
            status="Failure",
            user_agent="ua",
        )
        LoginLog.objects.create(
            username="signals_user",
            ip_address="203.0.113.20",
            status="Failure",
            user_agent="ua",
        )

        request = self.factory.post("/admin-login/")
        request.META["REMOTE_ADDR"] = "203.0.113.20"
        request.META["HTTP_USER_AGENT"] = "ua-test"

        result = authenticate(request=request, username="signals_user", password="wrong")
        self.assertIsNone(result)

        latest = LoginLog.objects.filter(username="signals_user", status="Failure").latest(
            "timestamp"
        )
        self.assertTrue(latest.is_user_suspicious)
        self.assertTrue(latest.is_suspicious)
        self.assertEqual(latest.ip_address, "203.0.113.20")

    def test_review_post_save_triggers_weight_adjustment_branch(self):
        prefs = UserPreference.objects.create(
            user=self.user,
            favorite_cuisines=["thai"],
            dietary_restrictions=["vegetarian"],
            price_preference="$$",
            neighborhood_preference="",
            cuisine_weight=Decimal("1.00"),
            price_weight=Decimal("1.00"),
            dietary_weight=Decimal("1.00"),
            minimum_interactions_for_learning=1,
        )

        # success_rate < 0.5 so recalculate_user_recommendation_model enters adjust branch.
        RecalculatedRecommendation.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            recommendation_score=Decimal("80.00"),
            cuisine_score=Decimal("9.00"),
            price_score=Decimal("2.00"),
            dietary_score=Decimal("8.00"),
            user_interacted=True,
        )
        RecalculatedRecommendation.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            recommendation_score=Decimal("40.00"),
            cuisine_score=Decimal("3.00"),
            price_score=Decimal("8.00"),
            dietary_score=Decimal("2.00"),
            user_interacted=False,
        )
        RecalculatedRecommendation.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            recommendation_score=Decimal("45.00"),
            cuisine_score=Decimal("4.00"),
            price_score=Decimal("7.00"),
            dietary_score=Decimal("3.00"),
            user_interacted=False,
        )

        with patch(
            "nomz.signals.refresh_restaurant_composite", return_value={}
        ), patch(
            "nomz.models.RecalculatedRecommendation.calculate_accuracy_from_interactions",
            return_value=None,
        ):
            Review.objects.create(
                restaurant=self.restaurant,
                user=self.user,
                rating=4,
                comment="trigger learning",
            )

        prefs.refresh_from_db()
        self.assertEqual(prefs.cuisine_weight, Decimal("1.05"))
        self.assertEqual(prefs.price_weight, Decimal("0.95"))
        self.assertEqual(prefs.dietary_weight, Decimal("1.05"))
        self.assertIn("Adjusted weights:", prefs.last_weights_adjustment_reason or "")
