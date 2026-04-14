from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.utils import timezone

from .models import (
    CompositeScoreAnomaly,
    CompositeScoreHistory,
    Restaurant,
    SystemAuditLog,
)
from .scoring import (
    _detect_score_anomalies,
    _safe_float,
    refresh_restaurant_composite,
    refresh_restaurants_composite,
)


class ScoringHelpersTests(TestCase):
    def test_safe_float_handles_none_invalid_and_numeric_values(self):
        self.assertIsNone(_safe_float(None))
        self.assertIsNone(_safe_float("not-a-number"))
        self.assertEqual(_safe_float("12.25"), 12.25)
        self.assertEqual(_safe_float(5), 5.0)

    def test_detect_score_anomalies_returns_expected_anomaly_types(self):
        old_inspection = timezone.localdate() - timedelta(days=400)
        score_data = {
            "composite_score": Decimal("92.50"),
            "review_count": 1,
            "review_confidence": Decimal("0.10"),
            "last_inspection_date": old_inspection,
        }

        anomalies = _detect_score_anomalies(score_data, previous_score=60.0)
        anomaly_types = {a["type"] for a in anomalies}

        self.assertEqual(
            anomaly_types,
            {
                "large_delta",
                "low_confidence_high_score",
                "stale_inspection_high_score",
            },
        )

    def test_detect_score_anomalies_excludes_stale_branch_without_date(self):
        score_data = {
            "composite_score": Decimal("88.00"),
            "review_count": 1,
            "review_confidence": Decimal("0.10"),
            "last_inspection_date": None,
        }
        anomalies = _detect_score_anomalies(score_data, previous_score=None)
        anomaly_types = {a["type"] for a in anomalies}
        self.assertIn("low_confidence_high_score", anomaly_types)
        self.assertNotIn("stale_inspection_high_score", anomaly_types)


class RefreshRestaurantCompositeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="score_owner", password="pass12345")
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Scoring Test Restaurant",
            cuisine_type="other",
            price_range="$$",
            composite_score=Decimal("55.00"),
        )

    def test_refresh_restaurant_composite_persists_history_and_anomalies(self):
        payload = {
            "composite_score": Decimal("92.00"),
            "grade": "A",
            "grade_score": 98,
            "last_inspection_date": timezone.localdate() - timedelta(days=500),
            "inspection_component_score": Decimal("35.00"),
            "review_component_score": Decimal("30.00"),
            "price_value_score": Decimal("15.00"),
            "operational_score": Decimal("12.00"),
            "review_count": 1,
            "review_confidence": Decimal("0.05"),
            "score_breakdown": [{"label": "Inspection", "score": 35}],
            "weights": {"inspection": 0.4},
            "review_factor_scores": {"food": 4.5},
            "review_factor_averages": {"food": 4.2},
            "review_recency_score": 0.7,
            "violation_score": 0.8,
            "recency_score": 0.6,
        }

        with patch("nomz.scoring.compute_restaurant_composite_score", return_value=payload):
            result = refresh_restaurant_composite(
                self.restaurant,
                trigger_source=CompositeScoreHistory.TRIGGER_MANAGEMENT_COMMAND,
                triggered_by=self.owner,
                trigger_note="x" * 300,
            )

        self.restaurant.refresh_from_db()
        history = CompositeScoreHistory.objects.get(restaurant=self.restaurant)
        anomalies = CompositeScoreAnomaly.objects.filter(restaurant=self.restaurant)
        audit_log = SystemAuditLog.objects.filter(
            action="composite_score_anomaly_detected"
        ).first()

        self.assertEqual(self.restaurant.composite_score, Decimal("92.00"))
        self.assertEqual(history.previous_composite_score, Decimal("55.00"))
        self.assertEqual(history.delta_from_previous, Decimal("37.00"))
        self.assertEqual(len(history.trigger_note), 255)
        self.assertEqual(history.triggered_by, self.owner)
        self.assertTrue(history.is_anomalous)
        self.assertEqual(anomalies.count(), 3)
        self.assertIsNotNone(audit_log)
        self.assertEqual(result["anomaly_count"], 3)
        self.assertEqual(result["history_id"], history.id)

    def test_refresh_restaurant_composite_ignores_unauthenticated_trigger_user(self):
        payload = {
            "composite_score": Decimal("60.00"),
            "grade": "B",
            "grade_score": 80,
            "last_inspection_date": timezone.localdate(),
            "review_count": 5,
            "review_confidence": Decimal("0.7"),
        }

        with patch("nomz.scoring.compute_restaurant_composite_score", return_value=payload):
            refresh_restaurant_composite(
                self.restaurant,
                triggered_by=AnonymousUser(),
            )

        history = CompositeScoreHistory.objects.get(restaurant=self.restaurant)
        self.assertIsNone(history.triggered_by)


class RefreshRestaurantsCompositeTests(TestCase):
    def test_refresh_restaurants_composite_returns_refreshed_count(self):
        restaurants = [
            Restaurant.objects.create(
                name="Bulk Refresh One",
                cuisine_type="other",
                price_range="$$",
            ),
            Restaurant.objects.create(
                name="Bulk Refresh Two",
                cuisine_type="other",
                price_range="$$",
            ),
        ]

        with patch("nomz.scoring.refresh_restaurant_composite") as mock_refresh:
            refreshed = refresh_restaurants_composite(restaurants)

        self.assertEqual(refreshed, 2)
        self.assertEqual(mock_refresh.call_count, 2)
