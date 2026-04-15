import json
from importlib import import_module
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    InspectionRecord,
    RecalculatedRecommendation,
    Restaurant,
    Review,
    UserInteractionHistory,
    UserPreference,
    UserProfile,
)
from .restaurant_sorting import (
    calculate_historical_satisfaction_for_restaurant,
    calculate_time_weighted_interaction_boost,
    normalize_sort_key,
    recommend_restaurants_for_user,
    record_recommendations_for_accuracy_tracking,
    sort_restaurant_queryset,
)
from .scoring import _detect_score_anomalies, _safe_float


class _FakeQuerySet:
    def __init__(self, rows, clear_target=None):
        self._rows = rows
        self._clear_target = clear_target if clear_target is not None else rows

    def iterator(self):
        return iter(self._rows)

    def all(self):
        return self

    def delete(self):
        self._clear_target.clear()


class _FakeSearchManager:
    def __init__(self):
        self.rows = []
        self.bulk_calls = []

    def all(self):
        return _FakeQuerySet(self.rows, self.rows)

    def bulk_create(self, rows, batch_size=1000):
        self.bulk_calls.append((len(rows), batch_size))
        self.rows.extend(rows)


class _FakeRestaurantManager:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return _FakeQuerySet(self._rows, self._rows)


class _FakeRestaurantSearchModel:
    objects = _FakeSearchManager()

    def __init__(self, name, neighborhood, description, cuisine):
        self.name = name
        self.neighborhood = neighborhood
        self.description = description
        self.cuisine = cuisine


class _FakeRestaurantModel:
    def __init__(self, rows):
        self.objects = _FakeRestaurantManager(rows)


class _FakeApps:
    def __init__(self, restaurant_rows):
        self.restaurant_model = _FakeRestaurantModel(restaurant_rows)
        self.search_model = _FakeRestaurantSearchModel
        self.search_model.objects = _FakeSearchManager()

    def get_model(self, app_label, model_name):
        if (app_label, model_name) == ("nomz", "Restaurant"):
            return self.restaurant_model
        if (app_label, model_name) == ("nomz", "RestaurantSearch"):
            return self.search_model
        raise LookupError(model_name)


class MigrationBackfillFunctionTests(SimpleTestCase):
    def test_0006_backfill_and_reverse(self):
        migration = import_module("nomz.migrations.0006_restaurantsearch")
        restaurants = [
            type(
                "Row",
                (),
                {
                    "name": "A" * 220,
                    "neighborhood": "",
                    "borough": "Queens",
                    "description": None,
                    "cuisine": "",
                    "cuisine_type": "italian",
                },
            )(),
        ]
        apps = _FakeApps(restaurants)

        migration.backfill_restaurant_search(apps, None)
        self.assertEqual(len(apps.search_model.objects.rows), 1)
        created = apps.search_model.objects.rows[0]
        self.assertEqual(len(created.name), 200)
        self.assertEqual(created.neighborhood, "Queens")
        self.assertEqual(created.cuisine, "italian")
        self.assertEqual(created.description, "")

        migration.reverse_backfill_restaurant_search(apps, None)
        self.assertEqual(apps.search_model.objects.rows, [])

    def test_0007_rebuild_uses_cuisine_tags_and_reverse(self):
        migration = import_module("nomz.migrations.0007_rebuild_restaurantsearch")
        restaurants = [
            type(
                "Row",
                (),
                {
                    "name": "Tag Bistro",
                    "neighborhood": None,
                    "borough": "Brooklyn",
                    "description": "desc",
                    "cuisine": "",
                    "cuisine_type": "",
                    "cuisine_tags": ["  vegan ", "", "thai"],
                },
            )(),
        ]
        apps = _FakeApps(restaurants)

        migration.rebuild_restaurant_search(apps, None)
        self.assertEqual(len(apps.search_model.objects.rows), 1)
        created = apps.search_model.objects.rows[0]
        self.assertEqual(created.cuisine, "vegan, thai")
        self.assertEqual(created.neighborhood, "Brooklyn")

        migration.reverse_rebuild_restaurant_search(apps, None)
        self.assertEqual(apps.search_model.objects.rows, [])

    def test_0007_rebuild_flushes_in_batches_of_1000(self):
        migration = import_module("nomz.migrations.0007_rebuild_restaurantsearch")
        restaurants = [
            type(
                "Row",
                (),
                {
                    "name": f"Tag Bistro {i}",
                    "neighborhood": "N",
                    "borough": "B",
                    "description": "",
                    "cuisine": "thai",
                    "cuisine_type": "thai",
                    "cuisine_tags": [],
                },
            )()
            for i in range(1001)
        ]
        apps = _FakeApps(restaurants)

        migration.rebuild_restaurant_search(apps, None)

        self.assertEqual(len(apps.search_model.objects.rows), 1001)
        self.assertEqual(apps.search_model.objects.bulk_calls[0], (1000, 1000))
        self.assertEqual(apps.search_model.objects.bulk_calls[1], (1, 1000))


class RestaurantSortingGapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sort_gap_user", password="pass12345"
        )
        self.r1 = Restaurant.objects.create(
            name="Gap A",
            is_active=True,
            is_flagged=False,
            cuisine_type="vegetarian",
            cuisine_tags=["vegetarian"],
            price_range="$",
            grade_score_latest=50,
            composite_score=50,
        )
        self.r2 = Restaurant.objects.create(
            name="Gap B",
            is_active=True,
            is_flagged=False,
            cuisine_type="italian",
            cuisine_tags=[],
            price_range="$$$",
            grade_score_latest=90,
            composite_score=90,
        )
        InspectionRecord.objects.create(
            restaurant=self.r1,
            inspection_date=timezone.localdate(),
            inspection_key="gap-insp-1",
        )
        InspectionRecord.objects.create(
            restaurant=self.r1,
            inspection_date=timezone.localdate(),
            inspection_key="gap-insp-2",
        )

    def test_normalize_sort_key_default_and_alias(self):
        self.assertEqual(normalize_sort_key("score_desc"), "composite_desc")
        self.assertEqual(normalize_sort_key(""), "composite_desc")

    def test_sort_restaurant_queryset_exercises_all_named_branches(self):
        base = Restaurant.objects.filter(name__startswith="Gap")
        keys = [
            "composite_desc",
            "composite_asc",
            "rating_desc",
            "rating_asc",
            "price_asc",
            "price_desc",
            "popularity_desc",
            "popularity_asc",
            "name_asc",
            "name_desc",
            "unknown_sort",
        ]
        for key in keys:
            with self.subTest(key=key):
                results = list(sort_restaurant_queryset(base, key))
                self.assertGreaterEqual(len(results), 2)

    def test_recommend_restaurants_for_user_hits_vegetarian_branch(self):
        UserPreference.objects.create(
            user=self.user,
            favorite_cuisines=[],
            dietary_restrictions=["vegetarian"],
            neighborhood_preference="",
            price_preference="",
            minimum_interactions_for_learning=99,
        )

        result = recommend_restaurants_for_user(self.user, limit=5, use_learning=False)
        self.assertTrue(result)
        self.assertEqual(result[0].id, self.r1.id)

    def test_recommend_restaurants_hits_gluten_free_halal_kosher_branches(self):
        branch_cases = [
            ("gluten-free", ["gluten-free"], "GF Spot"),
            ("halal", ["halal"], "Halal Spot"),
            ("kosher", ["kosher"], "Kosher Spot"),
        ]
        for idx, (restriction, tags, name) in enumerate(branch_cases):
            with self.subTest(restriction=restriction):
                user = User.objects.create_user(
                    username=f"diet_user_{idx}",
                    password="pass12345",
                )
                UserPreference.objects.create(
                    user=user,
                    favorite_cuisines=[],
                    dietary_restrictions=[restriction],
                    neighborhood_preference="",
                    price_preference="",
                    minimum_interactions_for_learning=99,
                )
                Restaurant.objects.create(
                    name=name,
                    is_active=True,
                    is_flagged=False,
                    cuisine_type="other",
                    cuisine_tags=tags,
                    price_range="$$",
                    composite_score=70,
                )
                result = recommend_restaurants_for_user(
                    user, limit=3, use_learning=False
                )
                self.assertTrue(result)

    def test_recommend_restaurants_returns_empty_without_preference_record(self):
        another_user = User.objects.create_user(
            username="no_pref_user", password="pass12345"
        )
        self.assertEqual(recommend_restaurants_for_user(another_user), [])

    def test_recommend_restaurants_returns_empty_when_preferences_blank(self):
        UserPreference.objects.create(
            user=self.user,
            favorite_cuisines=[],
            dietary_restrictions=[],
            price_preference="",
            neighborhood_preference="",
        )
        self.assertEqual(recommend_restaurants_for_user(self.user), [])

    def test_recommend_restaurants_learning_flow_records_recommendations_and_updates_prefs(
        self,
    ):
        prefs = UserPreference.objects.create(
            user=self.user,
            favorite_cuisines=["vegetarian"],
            dietary_restrictions=["vegan"],
            price_preference="$",
            neighborhood_preference="",
            minimum_interactions_for_learning=1,
        )
        UserInteractionHistory.objects.create(
            user=self.user,
            restaurant=self.r1,
            interaction_type="view",
            created_at=timezone.now() - timezone.timedelta(days=2),
        )

        result = recommend_restaurants_for_user(self.user, limit=3, use_learning=True)
        prefs.refresh_from_db()
        rec = RecalculatedRecommendation.objects.filter(
            user=self.user,
            restaurant=self.r1,
        ).first()

        self.assertTrue(result)
        self.assertIsNotNone(rec)
        self.assertGreater(prefs.total_recommendations_received, 0)
        self.assertIsNotNone(prefs.last_recommendation_recalculated_at)

    def test_recommend_restaurants_quality_score_cast_error_is_handled(self):
        user = User.objects.create_user(
            username="float_error_user", password="pass12345"
        )
        UserPreference.objects.create(
            user=user,
            favorite_cuisines=["vegetarian"],
            dietary_restrictions=[],
            neighborhood_preference="",
            price_preference="",
            minimum_interactions_for_learning=99,
        )

        original_float = float

        def _patched_float(value):
            # Force the exception branch guarded in calculate_enhanced_score.
            if str(value) == str(self.r1.composite_score):
                raise TypeError("forced float conversion failure")
            return original_float(value)

        with patch("nomz.restaurant_sorting.float", side_effect=_patched_float):
            result = recommend_restaurants_for_user(user, limit=5, use_learning=False)

        self.assertTrue(result)


class RestaurantSortingHelperFunctionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="helper_user", password="pass12345"
        )
        self.restaurant = Restaurant.objects.create(
            name="Helper Thai Spot",
            cuisine_type="thai",
            price_range="$$",
            is_active=True,
            is_flagged=False,
        )
        self.other_restaurant = Restaurant.objects.create(
            name="Helper Other Spot",
            cuisine_type="mexican",
            price_range="$$",
            is_active=True,
            is_flagged=False,
        )

    def test_calculate_historical_satisfaction_for_restaurant_no_and_similar_reviews(
        self,
    ):
        self.assertEqual(
            calculate_historical_satisfaction_for_restaurant(
                self.user, self.restaurant
            ),
            0,
        )

        Review.objects.create(
            restaurant=self.restaurant,
            user=self.user,
            rating=5,
        )
        Review.objects.create(
            restaurant=self.other_restaurant,
            user=self.user,
            rating=1,
        )
        score = calculate_historical_satisfaction_for_restaurant(
            self.user, self.restaurant
        )
        self.assertGreater(score, 1.0)

    def test_calculate_time_weighted_interaction_boost_zero_and_capped(self):
        self.assertEqual(
            calculate_time_weighted_interaction_boost(self.user, self.restaurant), 0
        )

        for _ in range(8):
            UserInteractionHistory.objects.create(
                user=self.user,
                restaurant=self.restaurant,
                interaction_type="view",
                created_at=timezone.now() - timezone.timedelta(days=1),
            )
        boost = calculate_time_weighted_interaction_boost(self.user, self.restaurant)
        self.assertEqual(boost, 1.0)

    def test_record_recommendations_for_accuracy_tracking_writes_component_scores(self):
        recommendations = [self.restaurant]
        scored_restaurants = [((12.5, {"cuisine": 5, "price": 2}), self.restaurant)]
        record_recommendations_for_accuracy_tracking(
            self.user, recommendations, scored_restaurants
        )
        record = RecalculatedRecommendation.objects.get(
            user=self.user, restaurant=self.restaurant
        )
        self.assertEqual(float(record.recommendation_score), 12.5)
        self.assertEqual(record.recommendation_rank, 1)


class ScoringGapTests(SimpleTestCase):
    def test_safe_float_type_error_path_and_none(self):
        class _BadFloat:
            def __float__(self):
                raise TypeError("cannot float")

        self.assertIsNone(_safe_float(None))
        self.assertIsNone(_safe_float(_BadFloat()))

    def test_detect_score_anomalies_hits_low_confidence_and_stale_paths(self):
        score_data = {
            "composite_score": 85,
            "review_count": 1,
            "review_confidence": 0.1,
            "last_inspection_date": timezone.localdate() - timezone.timedelta(days=366),
        }
        anomalies = _detect_score_anomalies(score_data, previous_score=None)
        kinds = {a["type"] for a in anomalies}
        self.assertIn("low_confidence_high_score", kinds)
        self.assertIn("stale_inspection_high_score", kinds)


class SpaAuthCoverageGapTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "pass12345"
        self.user = User.objects.create_user(
            username="spa_auth_user",
            email="spa_auth_user@example.com",
            password=self.password,
        )
        UserProfile.objects.create(user=self.user, role="diner")

    def test_auth_login_invalid_json_returns_error(self):
        response = self.client.post(
            reverse("api_auth_login"),
            data="{not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON.")

    def test_auth_login_requires_username_and_password(self):
        response = self.client.post(
            reverse("api_auth_login"),
            data=json.dumps({"username": "spa_auth_user", "password": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("required", response.json()["error"])

    @patch("nomz.spa_api.user_has_device", return_value=True)
    def test_auth_login_sets_pending_2fa_when_device_exists(self, _mock_has_device):
        response = self.client.post(
            reverse("api_auth_login"),
            data=json.dumps({"username": "spa_auth_user", "password": self.password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["requires_2fa"])
        self.assertFalse(payload["authenticated"])
        self.assertEqual(self.client.session.get("_2fa_user_id"), self.user.id)

    @patch("nomz.spa_api.user_has_device", return_value=False)
    def test_auth_login_success_without_2fa_device(self, _mock_has_device):
        response = self.client.post(
            reverse("api_auth_login"),
            data=json.dumps({"username": "spa_auth_user", "password": self.password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["username"], "spa_auth_user")

    def test_auth_login_invalid_credentials_returns_401(self):
        response = self.client.post(
            reverse("api_auth_login"),
            data=json.dumps({"username": "spa_auth_user", "password": "bad-password"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("username and password", response.json()["error"])

    def test_auth_admin_login_returns_session_when_staff_already_authenticated(self):
        staff = User.objects.create_user(
            username="spa_staff",
            password=self.password,
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse("api_auth_admin_login"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertTrue(response.json()["is_staff"])

    def test_auth_admin_login_invalid_json_returns_error(self):
        response = self.client.post(
            reverse("api_auth_admin_login"),
            data="{bad-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON.")

    def test_auth_admin_login_requires_all_fields(self):
        response = self.client.post(
            reverse("api_auth_admin_login"),
            data=json.dumps({"username": "admin", "password": "x", "security_code": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("required", response.json()["error"])

    @patch.dict("os.environ", {"ADMIN_SECURITY_CODE": "ADM123"}, clear=False)
    def test_auth_admin_login_invalid_credentials_path_returns_401(self):
        response = self.client.post(
            reverse("api_auth_admin_login"),
            data=json.dumps(
                {"username": "admin", "password": "wrong", "security_code": "ADM123"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())
        self.assertIn("__all__", response.json()["errors"])

    def test_auth_admin_login_field_error_returns_400_branch(self):
        response = self.client.post(
            reverse("api_auth_admin_login"),
            data=json.dumps(
                {
                    "username": "admin",
                    "password": "x",
                    "security_code": "x" * 30,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("security_code", response.json()["errors"])

    @patch("nomz.spa_api.AdminLoginForm")
    def test_auth_admin_login_success_logs_in_staff(self, mock_form_cls):
        staff = User.objects.create_user(
            username="patched_admin",
            password=self.password,
            is_staff=True,
            is_superuser=True,
        )
        mock_form = mock_form_cls.return_value
        mock_form.is_valid.return_value = True
        mock_form.get_user.return_value = staff

        response = self.client.post(
            reverse("api_auth_admin_login"),
            data=json.dumps(
                {
                    "username": "patched_admin",
                    "password": self.password,
                    "security_code": "ok",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertTrue(payload["is_staff"])

    def test_auth_2fa_verify_invalid_json_returns_error(self):
        response = self.client.post(
            reverse("api_auth_2fa_verify"),
            data="{invalid",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON.")

    def test_auth_2fa_verify_requires_pending_session(self):
        response = self.client.post(
            reverse("api_auth_2fa_verify"),
            data=json.dumps({"token": "123456"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("No pending two-factor", response.json()["error"])

    def test_auth_2fa_verify_requires_token(self):
        session = self.client.session
        session["_2fa_user_id"] = self.user.id
        session.save()
        response = self.client.post(
            reverse("api_auth_2fa_verify"),
            data=json.dumps({"token": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("required", response.json()["error"])

    def test_auth_2fa_verify_returns_invalid_session_for_missing_user(self):
        session = self.client.session
        session["_2fa_user_id"] = 999999
        session.save()
        response = self.client.post(
            reverse("api_auth_2fa_verify"),
            data=json.dumps({"token": "123456"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid session.")

    @patch("nomz.spa_api.match_token")
    def test_auth_2fa_verify_success_clears_pending_and_authenticates(self, mock_match_token):
        session = self.client.session
        session["_2fa_user_id"] = self.user.id
        session.save()
        mock_match_token.return_value = object()

        response = self.client.post(
            reverse("api_auth_2fa_verify"),
            data=json.dumps({"token": "654321"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["username"], self.user.username)
        self.assertNotIn("_2fa_user_id", self.client.session)

    @patch("nomz.spa_api.match_token", return_value=None)
    def test_auth_2fa_verify_invalid_code_returns_401(self, _mock_match_token):
        session = self.client.session
        session["_2fa_user_id"] = self.user.id
        session.save()

        response = self.client.post(
            reverse("api_auth_2fa_verify"),
            data=json.dumps({"token": "000000"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid authentication code", response.json()["error"])
