from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase


class _CountableQS:
    def __init__(self, count_value=0, update_value=0):
        self._count_value = count_value
        self._update_value = update_value

    def distinct(self):
        return self

    def count(self):
        return self._count_value

    def update(self, **_kwargs):
        return self._update_value


class _CandidateQS:
    def __init__(self, restaurant_ids):
        self.restaurant_ids = restaurant_ids

    def distinct(self):
        return self

    def filter(self, **_kwargs):
        return self

    def values_list(self, *_args, **_kwargs):
        return self.restaurant_ids


class _IterableQS:
    def __init__(self, rows):
        self.rows = rows

    def only(self, *_args):
        return self

    def __iter__(self):
        return iter(self.rows)


class ManagementCommandCoverageTests(SimpleTestCase):
    def test_cleanup_restaurant_data_apply_prints_success_summary(self):
        orphan_qs = _CountableQS(count_value=3, update_value=2)
        geocoded_qs = _CountableQS(count_value=14)
        eligible_qs = _CountableQS(count_value=11)

        stdout = StringIO()
        with patch(
            "nomz.management.commands.cleanup_restaurant_data.Restaurant.objects.filter",
            side_effect=[orphan_qs, geocoded_qs, eligible_qs],
        ):
            call_command("cleanup_restaurant_data", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Candidates to deactivate: 3", output)
        self.assertIn("Geocoded active restaurants: 14", output)
        self.assertIn("Current map/API eligible restaurants: 11", output)
        self.assertIn("Deactivated 2 restaurant(s).", output)

    def test_seed_synthetic_reviews_apply_prints_success_summary(self):
        candidate_qs = _CandidateQS([101])
        lookup_qs = _IterableQS(
            [
                SimpleNamespace(
                    id=101,
                    name="Synthetic Spot",
                    borough="Manhattan",
                    cuisine_type="other",
                    price_range="$$",
                )
            ]
        )
        refresh_qs = _IterableQS([SimpleNamespace(id=101)])

        filter_calls = {"id_in": 0}

        def restaurant_filter_side_effect(**kwargs):
            if kwargs == {"inspections__isnull": True}:
                return candidate_qs
            if "id__in" in kwargs:
                filter_calls["id_in"] += 1
                return lookup_qs if filter_calls["id_in"] == 1 else refresh_qs
            raise AssertionError(f"Unexpected filter kwargs: {kwargs}")

        reviewer_calls = {"count": 0}

        def user_get_or_create_side_effect(**_kwargs):
            reviewer_calls["count"] += 1
            reviewer = SimpleNamespace(id=reviewer_calls["count"])
            return reviewer, True

        stdout = StringIO()
        with patch(
            "nomz.management.commands.seed_synthetic_reviews.Restaurant.objects.filter",
            side_effect=restaurant_filter_side_effect,
        ), patch(
            "nomz.management.commands.seed_synthetic_reviews.User.objects.get_or_create",
            side_effect=user_get_or_create_side_effect,
        ), patch(
            "nomz.management.commands.seed_synthetic_reviews.Review.objects.bulk_create"
        ) as mock_bulk_create, patch(
            "nomz.management.commands.seed_synthetic_reviews.refresh_restaurant_composite"
        ) as mock_refresh:
            call_command(
                "seed_synthetic_reviews",
                "--apply",
                "--reviewer-pool-size",
                "5",
                "--min-reviews",
                "1",
                "--max-reviews",
                "1",
                "--seed",
                "123",
                stdout=stdout,
            )

        output = stdout.getvalue()
        self.assertIn("Candidate restaurants without inspections/reviews: 1", output)
        self.assertIn("Synthetic reviews seeded successfully:", output)
        self.assertIn("across 1 restaurant(s).", output)
        self.assertTrue(mock_bulk_create.called)
        self.assertEqual(mock_refresh.call_count, 1)
