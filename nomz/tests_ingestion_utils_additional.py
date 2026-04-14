from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from nomz.ingestion.utils.normalization import (
    first_non_empty,
    normalize_text,
    sanitize_nyc_coordinate_pair,
    split_list_fields,
    to_decimal_str,
    to_str,
)
from nomz.ingestion.utils.score import (
    _average,
    _grade_score,
    _normalize_5_to_100,
    _operational_signal,
    _price_value_signal,
    _review_time_weight,
    _recency_score,
    _review_signal,
    _to_local_date,
    _violation_score,
    compute_composite_score_from_records,
    compute_restaurant_composite_score,
)
from nomz.models import InspectionRecord, Restaurant, Review


class IngestionNormalizationUtilsTests(SimpleTestCase):
    def test_to_str_and_normalize_text_clean_values(self):
        self.assertEqual(to_str(None), "")
        self.assertEqual(to_str("  abc  "), "abc")
        self.assertEqual(to_str(123), "123")
        self.assertEqual(normalize_text("foo\u00a0 bar   baz"), "FOO BAR BAZ")

    def test_first_non_empty_returns_first_trimmed_value(self):
        row = {"primary": "   ", "fallback": "  value ", "other": "x"}
        self.assertEqual(first_non_empty(row, ["primary", "fallback", "other"]), "value")
        self.assertEqual(first_non_empty({}, ["missing"]), "")

    def test_to_decimal_str_parses_and_quantizes(self):
        self.assertIsNone(to_decimal_str(None))
        self.assertIsNone(to_decimal_str("not-a-number"))
        self.assertIsNone(to_decimal_str("   "))
        self.assertEqual(to_decimal_str("40.7128"), "40.712800")
        self.assertEqual(to_decimal_str("1,234.5"), "1234.500000")

    def test_sanitize_nyc_coordinate_pair_valid_and_invalid_cases(self):
        self.assertEqual(
            sanitize_nyc_coordinate_pair("40.7128", "-74.0060"),
            ("40.712800", "-74.006000"),
        )
        self.assertEqual(sanitize_nyc_coordinate_pair("0", "0"), (None, None))
        self.assertEqual(sanitize_nyc_coordinate_pair("42.0", "-74.0"), (None, None))
        self.assertEqual(sanitize_nyc_coordinate_pair("40.7", "bad"), ("40.700000", None))

    def test_sanitize_nyc_coordinate_pair_handles_decimal_conversion_exception(self):
        with patch(
            "nomz.ingestion.utils.normalization.to_decimal_str",
            side_effect=["40.712800", "-74.006000"],
        ), patch("nomz.ingestion.utils.normalization.Decimal", side_effect=ValueError):
            self.assertEqual(
                sanitize_nyc_coordinate_pair("40.7128", "-74.0060"),
                (None, None),
            )

    def test_split_list_fields_supports_lists_and_delimited_strings(self):
        self.assertEqual(split_list_fields(None), [])
        self.assertEqual(
            split_list_fields([" thai ", "Italian", "", None]),
            ["THAI", "ITALIAN"],
        )
        self.assertEqual(
            split_list_fields("thai|italian, mexican"),
            ["THAI", "ITALIAN", "MEXICAN"],
        )


class IngestionScoreUtilsPureFunctionTests(SimpleTestCase):
    def test_to_local_date_grade_violation_and_recency_helpers(self):
        today = timezone.localdate()
        self.assertIsNone(_to_local_date(None))
        self.assertIsNone(_to_local_date("2026-01-01"))
        self.assertEqual(_to_local_date(today), today)
        self.assertEqual(_to_local_date(datetime(2025, 1, 2, 5, 0, 0)), date(2025, 1, 2))

        self.assertEqual(_grade_score("A"), 95)
        self.assertEqual(_grade_score("B"), 72)
        self.assertEqual(_grade_score("C"), 42)
        self.assertEqual(_grade_score("not graded"), 62)
        self.assertEqual(_grade_score("Z"), 50)

        self.assertEqual(_violation_score(0, 0), 100.0)
        self.assertEqual(_violation_score(3, 0), 72.5)
        self.assertEqual(_recency_score(None, today), 35.0)
        self.assertEqual(_recency_score(today, today), 100.0)
        self.assertEqual(_recency_score(today - timedelta(days=120), today), 74.0)
        self.assertEqual(_recency_score(today - timedelta(days=500), today), 40.0)
        self.assertEqual(_review_time_weight(10), 1.0)
        self.assertEqual(_review_time_weight(60), 0.85)
        self.assertEqual(_review_time_weight(120), 0.70)
        self.assertEqual(_review_time_weight(300), 0.55)
        self.assertEqual(_review_time_weight(500), 0.40)
        self.assertIsNone(_average([]))
        self.assertEqual(_normalize_5_to_100(None), 60.0)

    def test_price_value_and_operational_signal_branches(self):
        self.assertEqual(_price_value_signal("$$", None), 58.0)

        class _DiningProfile:
            def __init__(self, status):
                self.license_status = status

        class _RestaurantObj:
            def __init__(self, is_active, temp, flagged, license_status):
                self.is_active = is_active
                self.is_temporarily_unavailable = temp
                self.is_flagged = flagged
                self.hours_open = "09:00"
                self.hours_close = "21:00"
                self.latitude = Decimal("40.7")
                self.longitude = Decimal("-74.0")
                self.dining_out_profile = _DiningProfile(license_status)

        active = _RestaurantObj(True, False, False, "active")
        penalized = _RestaurantObj(False, True, True, "suspended")
        self.assertGreater(_operational_signal(active), _operational_signal(penalized))

    def test_review_signal_no_reviews_returns_neutral_defaults(self):
        signal = _review_signal([], timezone.localdate())
        self.assertEqual(signal["review_count"], 0)
        self.assertEqual(signal["confidence"], 0.0)
        self.assertEqual(signal["review_component_score"], 60.0)
        self.assertEqual(signal["review_recency_score"], 60.0)

    def test_compute_composite_score_from_records_uses_latest_row(self):
        class _Inspection:
            def __init__(self, grade, critical, noncritical, inspection_date):
                self.grade = grade
                self.critical_violations = critical
                self.noncritical_violations = noncritical
                self.inspection_date = inspection_date

        reference = date(2026, 4, 14)
        latest = _Inspection("A", 0, 1, reference - timedelta(days=10))
        older = _Inspection("C", 4, 8, reference - timedelta(days=200))
        result = compute_composite_score_from_records([latest, older], now=reference)

        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["grade_score"], 95)
        self.assertGreater(result["composite_score"], 80.0)

    def test_compute_composite_score_from_records_empty_records(self):
        result = compute_composite_score_from_records([], now=date(2026, 4, 14))
        self.assertEqual(result["grade"], "")
        self.assertEqual(result["grade_score"], 50)
        self.assertIsNone(result["last_inspection_date"])


class IngestionScoreComputationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="score_user", password="pass12345")
        self.restaurant = Restaurant.objects.create(
            name="Utility Score Spot",
            owner=self.user,
            cuisine_type="other",
            price_range="$$",
            is_active=True,
            is_temporarily_unavailable=False,
            is_flagged=False,
            hours_open="09:00",
            hours_close="21:00",
            latitude=Decimal("40.712800"),
            longitude=Decimal("-74.006000"),
        )

    def test_compute_restaurant_composite_score_review_present_uses_review_dominant_weights(
        self,
    ):
        InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2026, 1, 5),
            inspection_key="u-score-review-path",
            grade="B",
            critical_violations=1,
            noncritical_violations=2,
        )
        Review.objects.create(
            restaurant=self.restaurant,
            user=self.user,
            rating=5,
            food_quality_rating=5,
            service_quality_rating=4,
            ambience_rating=4,
            location_rating=4,
            value_rating=4,
            dietary_accommodation_rating=4,
            cleanliness_rating=5,
        )

        result = compute_restaurant_composite_score(self.restaurant)
        self.assertEqual(result["weights"]["review_experience"], 0.65)
        self.assertEqual(result["review_count"], 1)
        self.assertTrue(result["score_breakdown"])

    def test_compute_restaurant_composite_score_no_reviews_with_inspection_uses_inspection_leaning_weights(
        self,
    ):
        InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2026, 2, 10),
            inspection_key="u-score-inspection-path",
            grade="A",
            critical_violations=0,
            noncritical_violations=1,
        )

        result = compute_restaurant_composite_score(self.restaurant)
        self.assertEqual(result["review_count"], 0)
        self.assertEqual(result["weights"]["inspection_hygiene"], 0.75)
        self.assertEqual(result["weights"]["review_experience"], 0.05)

    def test_compute_restaurant_composite_score_no_reviews_no_inspection_uses_cold_start_weights(
        self,
    ):
        result = compute_restaurant_composite_score(self.restaurant)
        self.assertEqual(result["review_count"], 0)
        self.assertEqual(result["weights"]["operational_reliability"], 0.40)
        self.assertEqual(result["grade"], "")

    def test_compute_restaurant_composite_score_as_of_date_filters_future_records(self):
        InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2026, 1, 1),
            inspection_key="u-score-old-inspection",
            grade="C",
            critical_violations=3,
            noncritical_violations=4,
        )
        InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2026, 4, 1),
            inspection_key="u-score-new-inspection",
            grade="A",
            critical_violations=0,
            noncritical_violations=0,
        )
        older_review = Review.objects.create(
            restaurant=self.restaurant,
            user=self.user,
            rating=2,
            value_rating=2,
        )
        newer_user = User.objects.create_user(username="score_user_2", password="pass12345")
        newer_review = Review.objects.create(
            restaurant=self.restaurant,
            user=newer_user,
            rating=5,
            value_rating=5,
        )

        Review.objects.filter(pk=older_review.pk).update(
            created_at=timezone.now() - timedelta(days=80)
        )
        Review.objects.filter(pk=newer_review.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )

        as_of = timezone.localdate() - timedelta(days=30)
        result = compute_restaurant_composite_score(self.restaurant, as_of_date=as_of)

        self.assertEqual(result["grade"], "C")
        self.assertEqual(result["review_count"], 1)
