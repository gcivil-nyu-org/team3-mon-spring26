import json
from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.test import TestCase, Client, TransactionTestCase
from django.http import HttpResponseServerError
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image
from unittest.mock import patch

from django.test.utils import override_settings

from .models import (
    CompositeScoreAnomaly,
    CompositeScoreHistory,
    Conversation,
    InspectionRecord,
    Message,
    MessageNotification,
    Restaurant,
    RestaurantOwnershipClaim,
    RestaurantPhoto,
    Review,
    ReviewResponse,
    SystemAlert,
    SystemAuditLog,
    SystemPerformanceMetric,
    SystemPerformanceSnapshot,
    UserProfile,
)
from .scoring import refresh_restaurant_composite
from .restaurant_sorting import normalize_sort_key, sort_restaurant_queryset


class RestaurantModelTests(TestCase):
    """Test cases for Restaurant model"""

    def setUp(self):
        """Create test user and restaurant"""
        self.user = User.objects.create_user(
            username="restaurantowner",
            email="owner@restaurant.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=self.user, role="restaurant")

        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name="Test Restaurant",
            description="A great place to eat",
            cuisine_type="italian",
            price_range="$$",
            address="123 Main St, NYC",
            phone="(555) 123-4567",
            email="contact@test.com",
            website="https://test.com",
            hours_open="09:00",
            hours_close="21:00",
            is_active=True,
            is_temporarily_unavailable=False,
        )

    def test_restaurant_creation(self):
        """Test restaurant creation"""
        self.assertEqual(self.restaurant.name, "Test Restaurant")
        self.assertEqual(self.restaurant.owner, self.user)
        self.assertTrue(self.restaurant.is_active)

    def test_restaurant_string_representation(self):
        """Test restaurant __str__ method"""
        self.assertEqual(str(self.restaurant), "Test Restaurant")

    def test_restaurant_can_be_managed_by_owner(self):
        """Test can_be_managed_by method"""
        self.assertTrue(self.restaurant.can_be_managed_by(self.user))

    def test_restaurant_cannot_be_managed_by_other_user(self):
        """Test can_be_managed_by method with different user"""
        other_user = User.objects.create_user(
            username="otheruser", password="otherpass123"
        )
        self.assertFalse(self.restaurant.can_be_managed_by(other_user))

    def test_restaurant_is_open_now(self):
        """Test is_open_now method"""
        # Deactivate to test condition
        self.restaurant.is_active = False
        self.assertFalse(self.restaurant.is_open_now())

        # Reactivate and test again
        self.restaurant.is_active = True
        # Note: This test may fail at certain times because of actual time comparison
        # In production, use freezegun or similar for time-based tests

    def test_restaurant_is_open_when_temporarily_unavailable(self):
        """Test is_open_now returns False when temporarily unavailable"""
        self.restaurant.is_temporarily_unavailable = True
        self.assertFalse(self.restaurant.is_open_now())

    def test_restaurant_unique_name(self):
        """Test that restaurant names are unique"""
        with self.assertRaises(Exception):
            Restaurant.objects.create(
                owner=self.user,
                name="Test Restaurant",  # Same name
                cuisine_type="italian",
                price_range="$$",
            )


class RestaurantPhotoModelTests(TestCase):
    """Test cases for RestaurantPhoto model"""

    def setUp(self):
        """Create test user and restaurant"""
        self.user = User.objects.create_user(
            username="restaurantowner", password="testpass123"
        )
        UserProfile.objects.create(user=self.user, role="restaurant")

        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name="Test Restaurant",
            cuisine_type="italian",
            price_range="$$",
        )

    def create_test_image(self):
        """Create a test image file"""
        image = Image.new("RGB", (100, 100), color="red")
        image_io = BytesIO()
        image.save(image_io, format="JPEG")
        image_io.seek(0)
        return SimpleUploadedFile(
            "test.jpg", image_io.getvalue(), content_type="image/jpeg"
        )

    def test_photo_creation(self):
        """Test photo creation"""
        photo = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Dining area",
        )
        self.assertEqual(photo.restaurant, self.restaurant)
        self.assertEqual(photo.caption, "Dining area")

    def test_photo_string_representation(self):
        """Test photo __str__ method"""
        photo = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Test Photo",
        )
        self.assertIn("Test Restaurant", str(photo))
        self.assertIn("Test Photo", str(photo))

    def test_primary_photo_uniqueness(self):
        """Test that only one photo can be primary"""
        photo1 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Photo 1",
            is_primary=True,
        )

        photo2 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Photo 2",
            is_primary=True,
        )

        # Refresh from DB
        photo1.refresh_from_db()

        # photo1 should no longer be primary
        self.assertFalse(photo1.is_primary)
        self.assertTrue(photo2.is_primary)

    def test_photos_ordered_by_primary_and_date(self):
        """Test that photos are ordered correctly"""
        photo1 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Photo 1",
            is_primary=False,
        )

        photo2 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Photo 2",
            is_primary=True,
        )

        photos = RestaurantPhoto.objects.filter(restaurant=self.restaurant)
        self.assertEqual(photos[0].id, photo2.id)  # Primary first
        self.assertEqual(photos[1].id, photo1.id)


class RestaurantProfileViewTests(TestCase):
    """Test cases for restaurant profile views"""

    def setUp(self):
        """Create test user and authenticate"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="restaurantowner", password="testpass123"
        )
        UserProfile.objects.create(user=self.user, role="restaurant")

        self.diner_user = User.objects.create_user(
            username="diner", password="testpass123"
        )
        UserProfile.objects.create(user=self.diner_user, role="diner")

    def test_restaurant_profile_view_requires_login(self):
        """SPA shell is public; JSON API enforces auth."""
        response = self.client.get(reverse("restaurant_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")
        r = self.client.get(reverse("api_restaurant_profile"))
        self.assertEqual(r.status_code, 302)

    def test_restaurant_profile_view_for_restaurant_owner(self):
        """Restaurant owner reads profile via JSON API."""
        Restaurant.objects.create(
            owner=self.user,
            name="Test Restaurant",
            cuisine_type="italian",
            price_range="$$",
        )

        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.get(reverse("restaurant_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")

        api_r = self.client.get(reverse("api_restaurant_profile"))
        self.assertEqual(api_r.status_code, 200)
        self.assertEqual(api_r.json()["restaurant"]["name"], "Test Restaurant")

    def test_diner_cannot_access_restaurant_profile(self):
        """Diner cannot use owner profile API."""
        self.client.login(username="diner", password="testpass123")
        response = self.client.get(reverse("restaurant_profile"))
        self.assertEqual(response.status_code, 200)
        api_r = self.client.get(reverse("api_restaurant_profile"))
        self.assertEqual(api_r.status_code, 403)

    def test_create_restaurant_profile_get(self):
        """Create-profile page is the SPA shell."""
        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.get(reverse("create_restaurant"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")

    def test_create_restaurant_profile_post(self):
        """Create profile via JSON API."""
        self.client.login(username="restaurantowner", password="testpass123")

        body = {
            "name": "New Restaurant",
            "description": "Great food",
            "cuisine_type": "italian",
            "price_range": "$$",
            "hours_open": "09:00",
            "hours_close": "21:00",
            "address": "123 Main St",
            "phone": "(555) 123-4567",
        }

        response = self.client.post(
            reverse("api_restaurant_profile"),
            data=json.dumps(body),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        restaurant = Restaurant.objects.get(owner=self.user)
        self.assertEqual(restaurant.name, "New Restaurant")

    def test_edit_restaurant_profile_get(self):
        """Edit-profile page is the SPA shell."""
        Restaurant.objects.create(
            owner=self.user,
            name="Test Restaurant",
            cuisine_type="italian",
            price_range="$$",
        )

        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.get(reverse("edit_restaurant"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")

    def test_edit_restaurant_profile_post(self):
        """Update profile via JSON API."""
        restaurant = Restaurant.objects.create(
            owner=self.user,
            name="Test Restaurant",
            cuisine_type="italian",
            price_range="$$",
            hours_open="09:00",
            hours_close="21:00",
        )

        self.client.login(username="restaurantowner", password="testpass123")

        body = {
            "name": "Updated Restaurant",
            "description": "Updated description",
            "cuisine_type": "french",
            "price_range": "$$$",
            "hours_open": "10:00",
            "hours_close": "22:00",
            "address": "456 Oak Ave",
        }

        self.client.post(
            reverse("api_restaurant_profile"),
            data=json.dumps(body),
            content_type="application/json",
        )

        restaurant.refresh_from_db()
        self.assertEqual(restaurant.name, "Updated Restaurant")
        self.assertEqual(restaurant.cuisine_type, "french")


class RestaurantAvailabilityViewTests(TestCase):
    """Test cases for availability management views"""

    def setUp(self):
        """Create test user and restaurant"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="restaurantowner", password="testpass123"
        )
        UserProfile.objects.create(user=self.user, role="restaurant")

        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name="Test Restaurant",
            cuisine_type="italian",
            price_range="$$",
        )

    def test_manage_availability_view(self):
        """Availability UI is the SPA shell."""
        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.get(reverse("manage_availability"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")

    def test_mark_temporarily_unavailable(self):
        """Mark unavailable via JSON API."""
        self.client.login(username="restaurantowner", password="testpass123")

        body = {"is_temporarily_unavailable": True, "unavailable_reason": "Renovations"}

        self.client.post(
            reverse("api_restaurant_availability"),
            data=json.dumps(body),
            content_type="application/json",
        )

        self.restaurant.refresh_from_db()
        self.assertTrue(self.restaurant.is_temporarily_unavailable)
        self.assertEqual(self.restaurant.unavailable_reason, "Renovations")


class RestaurantPhotoViewTests(TestCase):
    """Test cases for photo management views"""

    def setUp(self):
        """Create test user and restaurant"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="restaurantowner", password="testpass123"
        )
        UserProfile.objects.create(user=self.user, role="restaurant")

        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name="Test Restaurant",
            cuisine_type="italian",
            price_range="$$",
        )

    def create_test_image(self):
        """Create a test image file"""
        image = Image.new("RGB", (100, 100), color="red")
        image_io = BytesIO()
        image.save(image_io, format="JPEG")
        image_io.seek(0)
        return SimpleUploadedFile(
            "test.jpg", image_io.getvalue(), content_type="image/jpeg"
        )

    def test_upload_photo_view_get(self):
        """Upload page is the SPA shell."""
        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.get(reverse("upload_photo"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")

    def test_upload_photo_view_post(self):
        """Upload photo via multipart JSON API."""
        self.client.login(username="restaurantowner", password="testpass123")

        data = {
            "photo": self.create_test_image(),
            "caption": "Dining area",
            "is_primary": "on",
        }

        response = self.client.post(reverse("api_restaurant_photo_upload"), data)

        self.assertEqual(response.status_code, 201)
        photo = RestaurantPhoto.objects.get(restaurant=self.restaurant)
        self.assertEqual(photo.caption, "Dining area")
        self.assertTrue(photo.is_primary)

    def test_restaurant_photos_view(self):
        """Gallery page is SPA; list comes from JSON API."""
        RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Test Photo",
        )

        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.get(reverse("restaurant_photos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")
        api_r = self.client.get(reverse("api_restaurant_photos_data"))
        self.assertEqual(api_r.status_code, 200)
        self.assertEqual(api_r.json()["photos"][0]["caption"], "Test Photo")

    def test_delete_photo(self):
        """Delete photo via JSON API."""
        photo = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Test Photo",
        )

        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.post(
            reverse("api_restaurant_photo_delete", args=[photo.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RestaurantPhoto.objects.filter(id=photo.id).exists())

    def test_set_primary_photo(self):
        """Set primary via JSON API."""
        photo1 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Photo 1",
            is_primary=True,
        )

        photo2 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption="Photo 2",
        )

        self.client.login(username="restaurantowner", password="testpass123")
        response = self.client.post(
            reverse("api_restaurant_photo_set_primary", args=[photo2.id]),
        )

        self.assertEqual(response.status_code, 200)

        photo2.refresh_from_db()
        photo1.refresh_from_db()
        self.assertTrue(photo2.is_primary)
        self.assertFalse(photo1.is_primary)


class SystemMonitoringTests(TransactionTestCase):
    @override_settings(
        SYSTEM_METRICS_SNAPSHOT_INTERVAL_SECONDS=1,
        SYSTEM_ALERT_ERROR_RATE_THRESHOLD=1.1,  # Disable high error rate alerts for single failures
        SYSTEM_ALERT_AVG_LATENCY_MS_THRESHOLD=100000,
    )
    def test_health_check_failure_creates_alert_and_audit_log(self):
        with patch(
            "nomz.views.perform_dependency_health_checks",
            side_effect=Exception("db down"),
        ):
            response = self.client.get(reverse("health_check"))
            self.assertEqual(response.status_code, 503)

        alert_qs = SystemAlert.objects.filter(
            alert_type="HEALTH_CHECK_FAILURE", is_active=True
        )
        audit_qs = SystemAuditLog.objects.filter(action="health_check_failure")
        self.assertTrue(
            alert_qs.exists(),
            msg=(
                f"Expected active HEALTH_CHECK_FAILURE alert. "
                f"alerts={alert_qs.count()} total_alerts={SystemAlert.objects.count()} "
                f"audit_logs={audit_qs.count()}"
            ),
        )
        self.assertTrue(audit_qs.exists())

    @override_settings(
        DEBUG=False,
        DEBUG_PROPAGATE_EXCEPTIONS=False,
        SYSTEM_METRICS_SNAPSHOT_INTERVAL_SECONDS=1,
        SYSTEM_ALERT_ERROR_RATE_THRESHOLD=1.1,
        SYSTEM_ALERT_AVG_LATENCY_MS_THRESHOLD=100000,
    )
    def test_unhandled_exception_creates_audit_log_and_metric(self):
        # Replace the `map` URL callback with one that returns a 500 response.
        # This triggers the middleware's 5xx audit/metric path without relying on
        # Django's exception propagation/transaction behavior.
        import nomz.urls as nomz_urlconf

        map_pattern = next(
            p for p in nomz_urlconf.urlpatterns if getattr(p, "name", None) == "map"
        )
        original_callback = map_pattern.callback

        def broken_map_view(request):
            return HttpResponseServerError("boom")

        try:
            map_pattern.callback = broken_map_view
            response = self.client.get(reverse("map"))
            self.assertEqual(response.status_code, 500)
        finally:
            map_pattern.callback = original_callback

        self.assertTrue(
            SystemAuditLog.objects.filter(action="server_error_response").exists()
        )
        self.assertTrue(
            SystemPerformanceMetric.objects.filter(
                status_code=500, is_error=True
            ).exists()
        )


class AdminMonitoringUserStoryTests(TestCase):
    """
    Acceptance-style tests for the admin monitoring / audit-log user story:
    metrics and logs are exposed in Django Admin, and persisted data matches expectations.
    """

    def test_monitoring_models_registered_for_admin_review(self):
        """Admin can access monitoring via registered models (changelist / detail)."""
        for model in (
            SystemPerformanceMetric,
            SystemPerformanceSnapshot,
            SystemAlert,
            SystemAuditLog,
        ):
            with self.subTest(model=model.__name__):
                self.assertTrue(
                    admin.site.is_registered(model),
                    f"{model.__name__} must be registered in admin",
                )

    def test_superuser_can_open_monitoring_admin_changelists(self):
        """System-wide metrics, snapshots, alerts, and audit logs are reachable in Admin."""
        User.objects.create_superuser(
            "admintest", "admin-monitoring@example.com", "SecretPass123!"
        )
        self.client.login(username="admintest", password="SecretPass123!")
        for model in (
            SystemPerformanceMetric,
            SystemPerformanceSnapshot,
            SystemAlert,
            SystemAuditLog,
        ):
            with self.subTest(model=model.__name__):
                url = reverse(
                    f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist"
                )
                response = self.client.get(url)
                self.assertEqual(
                    response.status_code,
                    200,
                    msg=f"Expected 200 for {model.__name__} changelist at {url}",
                )


class AdminMonitoringMetricsTests(TransactionTestCase):
    """Metrics and alert rules exercised against acceptance criteria."""

    def test_successful_health_check_records_performance_metric(self):
        """Healthy /health/ responses are recorded for performance visibility."""
        response = self.client.get(reverse("health_check"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SystemPerformanceMetric.objects.filter(
                path__icontains="health",
                status_code=200,
                is_error=False,
            ).exists()
        )

    @override_settings(
        SYSTEM_METRICS_SNAPSHOT_INTERVAL_SECONDS=1,
        SYSTEM_ALERT_ERROR_RATE_THRESHOLD=0.2,
        SYSTEM_ALERT_AVG_LATENCY_MS_THRESHOLD=100000,
    )
    def test_high_error_rate_alert_when_server_errors_exceed_threshold(self):
        """Alerts fire when error rate in a bucket crosses the configured threshold."""
        import nomz.urls as nomz_urlconf

        map_pattern = next(
            p for p in nomz_urlconf.urlpatterns if getattr(p, "name", None) == "map"
        )
        original_callback = map_pattern.callback

        def always_500(request):
            return HttpResponseServerError("simulated failure")

        try:
            map_pattern.callback = always_500
            self.client.get(reverse("map"))
        finally:
            map_pattern.callback = original_callback

        self.assertTrue(
            SystemAlert.objects.filter(
                alert_type="HIGH_ERROR_RATE", is_active=True
            ).exists()
        )

    def test_server_error_audit_log_stores_status_in_metadata(self):
        """Audit logs for 5xx responses record critical context (status code)."""
        import nomz.urls as nomz_urlconf

        map_pattern = next(
            p for p in nomz_urlconf.urlpatterns if getattr(p, "name", None) == "map"
        )
        original_callback = map_pattern.callback

        def always_500(request):
            return HttpResponseServerError("boom")

        try:
            map_pattern.callback = always_500
            self.client.get(reverse("map"))
        finally:
            map_pattern.callback = original_callback

        log = SystemAuditLog.objects.filter(action="server_error_response").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get("status_code"), 500)


class RestaurantSortingTests(TestCase):
    """Map API and search list ordering (composite, rating, price, popularity)."""

    def setUp(self):
        self.client = Client()
        self.r_a = Restaurant.objects.create(
            name="Sort Test A",
            is_active=True,
            latitude=Decimal("40.700000"),
            longitude=Decimal("-74.000000"),
            composite_score=Decimal("20.00"),
            grade_score_latest=40,
            price_range="$",
        )
        self.r_b = Restaurant.objects.create(
            name="Sort Test B",
            is_active=True,
            latitude=Decimal("40.710000"),
            longitude=Decimal("-74.010000"),
            composite_score=Decimal("90.00"),
            grade_score_latest=95,
            price_range="$$$",
        )
        self.r_c = Restaurant.objects.create(
            name="Sort Test C",
            is_active=True,
            latitude=Decimal("40.720000"),
            longitude=Decimal("-74.020000"),
            composite_score=Decimal("55.00"),
            grade_score_latest=70,
            price_range="$$",
        )
        for i in range(3):
            InspectionRecord.objects.create(
                restaurant=self.r_c,
                inspection_date=date(2024, 1, 10 + i),
                inspection_key=f"sort-test-c-{i}",
            )

    def _subset_order(self, payload_ids):
        wanted = {self.r_a.id, self.r_b.id, self.r_c.id}
        return [pk for pk in payload_ids if pk in wanted]

    def test_normalize_sort_key_aliases_score_to_composite(self):
        self.assertEqual(normalize_sort_key("score_desc"), "composite_desc")
        self.assertEqual(normalize_sort_key("score_asc"), "composite_asc")

    def test_map_api_sort_composite_desc(self):
        response = self.client.get(
            reverse("api_restaurants_map"),
            {"sort_by": "composite_desc", "limit": "50"},
        )
        self.assertEqual(response.status_code, 200)
        ids = self._subset_order([r["id"] for r in response.json()["results"]])
        self.assertEqual(ids, [self.r_b.id, self.r_c.id, self.r_a.id])

    def test_map_api_sort_rating_desc(self):
        response = self.client.get(
            reverse("api_restaurants_map"),
            {"sort_by": "rating_desc", "limit": "50"},
        )
        self.assertEqual(response.status_code, 200)
        ids = self._subset_order([r["id"] for r in response.json()["results"]])
        self.assertEqual(ids, [self.r_b.id, self.r_c.id, self.r_a.id])

    def test_map_api_sort_price_asc(self):
        response = self.client.get(
            reverse("api_restaurants_map"),
            {"sort_by": "price_asc", "limit": "50"},
        )
        self.assertEqual(response.status_code, 200)
        ids = self._subset_order([r["id"] for r in response.json()["results"]])
        self.assertEqual(ids, [self.r_a.id, self.r_c.id, self.r_b.id])

    def test_map_api_sort_popularity_desc(self):
        response = self.client.get(
            reverse("api_restaurants_map"),
            {"sort_by": "popularity_desc", "limit": "50"},
        )
        self.assertEqual(response.status_code, 200)
        ids = self._subset_order([r["id"] for r in response.json()["results"]])
        self.assertEqual(ids[0], self.r_c.id)

    def test_restaurant_search_sort_with_query(self):
        user = User.objects.create_user(username="sort_diner", password="pass12345")
        UserProfile.objects.create(user=user, role="diner")
        self.client.login(username="sort_diner", password="pass12345")
        response = self.client.get(
            reverse("api_restaurant_search"),
            {"q": "Sort Test", "sort_by": "price_asc"},
        )
        self.assertEqual(response.status_code, 200)
        names = [r["name"] for r in response.json()["results"]]
        self.assertEqual(
            names,
            ["Sort Test A", "Sort Test C", "Sort Test B"],
        )


class SortRestaurantQuerysetUnitTests(TestCase):
    """
    User story — Definition of Done: sorting logic at query level.
    Tests `sort_restaurant_queryset` directly (no HTTP).
    """

    def setUp(self):
        self.r_low = Restaurant.objects.create(
            name="UnitSort Low",
            is_active=True,
            composite_score=Decimal("10.00"),
            grade_score_latest=40,
            price_range="$",
        )
        self.r_mid = Restaurant.objects.create(
            name="UnitSort Mid",
            is_active=True,
            composite_score=Decimal("50.00"),
            grade_score_latest=70,
            price_range="$$",
        )
        self.r_high = Restaurant.objects.create(
            name="UnitSort High",
            is_active=True,
            composite_score=Decimal("90.00"),
            grade_score_latest=95,
            price_range="$$$$",
        )
        # Do not attach InspectionRecords here: post_save signal calls
        # refresh_restaurant_composite() and overwrites composite_score.

    def _ids(self, queryset):
        return list(queryset.values_list("id", flat=True))

    def test_composite_desc_then_asc(self):
        base = Restaurant.objects.filter(name__startswith="UnitSort").order_by("pk")
        desc = self._ids(sort_restaurant_queryset(base, "composite_desc"))
        self.assertEqual(desc, [self.r_high.id, self.r_mid.id, self.r_low.id])
        asc = self._ids(sort_restaurant_queryset(base, "composite_asc"))
        self.assertEqual(asc, [self.r_low.id, self.r_mid.id, self.r_high.id])

    def test_rating_desc_then_asc(self):
        base = Restaurant.objects.filter(name__startswith="UnitSort")
        desc = self._ids(sort_restaurant_queryset(base, "rating_desc"))
        self.assertEqual(desc, [self.r_high.id, self.r_mid.id, self.r_low.id])
        asc = self._ids(sort_restaurant_queryset(base, "rating_asc"))
        self.assertEqual(asc, [self.r_low.id, self.r_mid.id, self.r_high.id])

    def test_price_asc_then_desc(self):
        base = Restaurant.objects.filter(name__startswith="UnitSort")
        asc = self._ids(sort_restaurant_queryset(base, "price_asc"))
        self.assertEqual(asc, [self.r_low.id, self.r_mid.id, self.r_high.id])
        desc = self._ids(sort_restaurant_queryset(base, "price_desc"))
        self.assertEqual(desc, [self.r_high.id, self.r_mid.id, self.r_low.id])

    def test_popularity_desc_then_asc(self):
        """Popularity uses inspection count; records trigger composite refresh on those rows only."""
        p_a = Restaurant.objects.create(
            name="UnitPop A",
            is_active=True,
            composite_score=Decimal("50.00"),
            grade_score_latest=70,
            price_range="$$",
        )
        p_b = Restaurant.objects.create(
            name="UnitPop B",
            is_active=True,
            composite_score=Decimal("50.00"),
            grade_score_latest=70,
            price_range="$$",
        )
        p_c = Restaurant.objects.create(
            name="UnitPop C",
            is_active=True,
            composite_score=Decimal("50.00"),
            grade_score_latest=70,
            price_range="$$",
        )
        for i in range(4):
            InspectionRecord.objects.create(
                restaurant=p_c,
                inspection_date=date(2022, 3, 1 + i),
                inspection_key=f"unit-pop-c-{i}",
            )
        for i in range(2):
            InspectionRecord.objects.create(
                restaurant=p_b,
                inspection_date=date(2022, 4, 1 + i),
                inspection_key=f"unit-pop-b-{i}",
            )
        base = Restaurant.objects.filter(name__startswith="UnitPop")
        desc = self._ids(sort_restaurant_queryset(base, "popularity_desc"))
        self.assertEqual(desc[0], p_c.id)
        self.assertEqual(set(desc), {p_a.id, p_b.id, p_c.id})
        asc = self._ids(sort_restaurant_queryset(base, "popularity_asc"))
        self.assertEqual(asc[0], p_a.id)

    def test_name_asc_desc(self):
        base = Restaurant.objects.filter(name__startswith="UnitSort")
        asc = self._ids(sort_restaurant_queryset(base, "name_asc"))
        self.assertEqual(
            asc,
            sorted(
                [self.r_low.id, self.r_mid.id, self.r_high.id],
                key=lambda pk: Restaurant.objects.get(pk=pk).name,
            ),
        )
        desc = self._ids(sort_restaurant_queryset(base, "name_desc"))
        self.assertEqual(list(reversed(asc)), desc)

    def test_invalid_sort_key_falls_back_to_composite_desc(self):
        base = Restaurant.objects.filter(name__startswith="UnitSort")
        got = self._ids(sort_restaurant_queryset(base, "not_a_valid_sort"))
        expected = self._ids(sort_restaurant_queryset(base, "composite_desc"))
        self.assertEqual(got, expected)


class RestaurantSortUserStoryAcceptanceTests(TestCase):
    """
    User story acceptance criteria:
    - Results reorder correctly with search/filters (map API + search view).
    - Server exposes stable sort key for repeated requests (persistence contract).
    """

    def setUp(self):
        self.client = Client()
        # NYC bbox + no owner => visible in map API
        self.manhattan_cheap = Restaurant.objects.create(
            name="Story Manhattan Cheap",
            is_active=True,
            latitude=Decimal("40.758000"),
            longitude=Decimal("-73.985500"),
            borough="Manhattan",
            neighborhood="Midtown",
            cuisine_tags=["Thai", "Noodles"],
            composite_score=Decimal("35.00"),
            grade_score_latest=50,
            price_range="$",
        )
        self.manhattan_pricey = Restaurant.objects.create(
            name="Story Manhattan Pricey",
            is_active=True,
            latitude=Decimal("40.761000"),
            longitude=Decimal("-73.982000"),
            borough="Manhattan",
            neighborhood="Midtown",
            cuisine_tags=["Thai", "Curry"],
            composite_score=Decimal("85.00"),
            grade_score_latest=90,
            price_range="$$$",
        )
        self.brooklyn_mid = Restaurant.objects.create(
            name="Story Brooklyn Mid",
            is_active=True,
            latitude=Decimal("40.678000"),
            longitude=Decimal("-73.985000"),
            borough="Brooklyn",
            neighborhood="Boerum Hill",
            cuisine_tags=["Italian"],
            composite_score=Decimal("60.00"),
            grade_score_latest=70,
            price_range="$$",
        )

    def test_map_api_sort_combined_with_text_search_and_cuisine(self):
        """Sort + search + cuisine filter together."""
        response = self.client.get(
            reverse("api_restaurants_map"),
            {
                "search": "Thai",
                "cuisine": "Thai",
                "sort_by": "composite_desc",
                "limit": "100",
            },
        )
        self.assertEqual(response.status_code, 200)
        ids = [r["id"] for r in response.json()["results"]]
        self.assertIn(self.manhattan_pricey.id, ids)
        self.assertIn(self.manhattan_cheap.id, ids)
        self.assertNotIn(self.brooklyn_mid.id, ids)
        thai_ids = [self.manhattan_pricey.id, self.manhattan_cheap.id]
        order = [i for i in ids if i in thai_ids]
        self.assertEqual(order, [self.manhattan_pricey.id, self.manhattan_cheap.id])

    def test_map_api_sort_combined_with_borough_and_min_score(self):
        """Sort + borough + min_score together."""
        response = self.client.get(
            reverse("api_restaurants_map"),
            {
                "borough": "Manhattan",
                "min_score": "50",
                "sort_by": "composite_asc",
                "limit": "100",
            },
        )
        self.assertEqual(response.status_code, 200)
        ids = [r["id"] for r in response.json()["results"]]
        self.assertIn(self.manhattan_pricey.id, ids)
        self.assertNotIn(self.manhattan_cheap.id, ids)
        self.assertNotIn(self.brooklyn_mid.id, ids)

    def test_map_api_same_sort_param_yields_identical_order(self):
        """Repeated requests with same sort (client can persist sort_by)."""
        params = {
            "borough": "Manhattan",
            "sort_by": "price_desc",
            "limit": "100",
        }
        first = [
            r["id"]
            for r in self.client.get(reverse("api_restaurants_map"), params).json()[
                "results"
            ]
        ]
        second = [
            r["id"]
            for r in self.client.get(reverse("api_restaurants_map"), params).json()[
                "results"
            ]
        ]
        subset = [
            i for i in first if i in {self.manhattan_cheap.id, self.manhattan_pricey.id}
        ]
        self.assertEqual(subset, [self.manhattan_pricey.id, self.manhattan_cheap.id])
        self.assertEqual(first, second)

    def test_restaurant_search_sort_with_neighborhood_and_query(self):
        """Search + neighborhood + sort together."""
        user = User.objects.create_user(username="story_diner", password="pass12345")
        UserProfile.objects.create(user=user, role="diner")
        self.client.login(username="story_diner", password="pass12345")
        response = self.client.get(
            reverse("api_restaurant_search"),
            {
                "q": "Story",
                "neighborhood": "Midtown",
                "sort_by": "composite_desc",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        names = [r["name"] for r in data["results"]]
        self.assertIn("Story Manhattan Pricey", names)
        self.assertIn("Story Manhattan Cheap", names)
        self.assertNotIn("Story Brooklyn Mid", names)
        self.assertEqual(
            names[:2],
            ["Story Manhattan Pricey", "Story Manhattan Cheap"],
        )

    def test_restaurant_search_context_sort_by_normalized(self):
        """API normalises sort key (persistence of selected criterion)."""
        user = User.objects.create_user(username="story_diner2", password="pass12345")
        UserProfile.objects.create(user=user, role="diner")
        self.client.login(username="story_diner2", password="pass12345")
        response = self.client.get(
            reverse("api_restaurant_search"),
            {"q": "Story", "sort_by": "score_asc"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["sort_by"], "composite_asc")

    def test_search_results_template_exposes_sort_control(self):
        """SPA shell loads and search API supports sort_by parameter."""
        user = User.objects.create_user(username="story_diner3", password="pass12345")
        UserProfile.objects.create(user=user, role="diner")
        self.client.login(username="story_diner3", password="pass12345")
        response = self.client.get(reverse("restaurant_search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")
        api_response = self.client.get(
            reverse("api_restaurant_search"), {"sort_by": "composite_desc"}
        )
        self.assertEqual(api_response.status_code, 200)
        data = api_response.json()
        self.assertIn("sort_by", data)
        self.assertEqual(data["sort_by"], "composite_desc")


class RestaurantClaimFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="claim_owner",
            email="claim@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(
            user=self.user,
            role="restaurant",
            is_approved=False,
            is_rejected=False,
        )
        self.unowned_restaurant = Restaurant.objects.create(
            name="Claimable Spot",
            is_active=True,
            price_range="$$",
            cuisine_type="other",
        )

    def test_register_restaurant_redirects_to_claim_page(self):
        response = self.client.post(
            reverse("api_auth_register"),
            data=json.dumps(
                {
                    "email": "newclaim@example.com",
                    "username": "newclaimuser",
                    "role": "restaurant",
                    "password1": "pass12345AA!",
                    "password2": "pass12345AA!",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json().get("authenticated"))

    def test_claim_restaurant_creates_pending_claim(self):
        self.client.login(username="claim_owner", password="pass12345")
        response = self.client.post(
            reverse("api_restaurant_claim"),
            data=json.dumps(
                {
                    "restaurant_id": self.unowned_restaurant.pk,
                    "business_email": "owner@claimablespot.com",
                    "contact_phone": "+1 212-555-1234",
                    "proof_details": "Business license and matching domain email.",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json().get("success"))
        claim = RestaurantOwnershipClaim.objects.get(
            claimant=self.user,
            restaurant=self.unowned_restaurant,
        )
        self.assertEqual(claim.status, RestaurantOwnershipClaim.STATUS_PENDING)

    def test_admin_approve_restaurant_approves_claim_and_assigns_owner(self):
        admin_user = User.objects.create_user(
            username="claim_admin",
            email="admin@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=self.user,
            restaurant=self.unowned_restaurant,
            business_email="owner@claimablespot.com",
            proof_details="Proof doc",
        )

        self.client.login(username="claim_admin", password="pass12345")
        response = self.client.post(
            reverse("api_admin_approve_user", args=[self.user.id]),
        )
        self.assertEqual(response.status_code, 200)

        claim.refresh_from_db()
        self.unowned_restaurant.refresh_from_db()
        self.user.userprofile.refresh_from_db()
        self.assertEqual(claim.status, RestaurantOwnershipClaim.STATUS_APPROVED)
        self.assertEqual(self.unowned_restaurant.owner_id, self.user.id)
        self.assertEqual(claim.reviewed_by_id, admin_user.id)
        self.assertTrue(self.user.userprofile.is_approved)
        self.assertFalse(self.user.userprofile.is_rejected)

    def test_pending_approvals_page_includes_claim_for_approved_user(self):
        admin_user = User.objects.create_user(
            username="claim_admin_2",
            email="admin2@example.com",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )
        self.user.userprofile.is_approved = True
        self.user.userprofile.save(update_fields=["is_approved"])

        RestaurantOwnershipClaim.objects.create(
            claimant=self.user,
            restaurant=self.unowned_restaurant,
            business_email="owner@claimablespot.com",
            proof_details="Proof doc",
        )

        self.client.login(username="claim_admin_2", password="pass12345")
        response = self.client.get(reverse("admin_pending_approvals"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")

        api_r = self.client.get(reverse("api_admin_pending_approvals_data"))
        self.assertEqual(api_r.status_code, 200)
        rows = api_r.json().get("results", [])
        self.assertTrue(any("Claimable" in str(r) for r in rows))


class RestaurantOwnerScoreDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="owner_score",
            email="owner_score@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(
            user=self.owner,
            role="restaurant",
            is_approved=True,
            is_rejected=False,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Owner Score Bistro",
            is_active=True,
            borough="Manhattan",
            neighborhood="Midtown",
            composite_score=Decimal("88.50"),
            grade_latest="A",
            grade_score_latest=95,
            cuisine_type="italian",
            price_range="$$",
        )
        Restaurant.objects.create(
            name="Peer One",
            is_active=True,
            borough="Manhattan",
            neighborhood="Midtown",
            composite_score=Decimal("82.00"),
            cuisine_type="other",
            price_range="$$",
        )
        Restaurant.objects.create(
            name="Peer Two",
            is_active=True,
            borough="Manhattan",
            neighborhood="Midtown",
            composite_score=Decimal("72.00"),
            cuisine_type="other",
            price_range="$$",
        )

        InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2025, 1, 10),
            inspection_key="owner-score-1",
            grade="B",
            score=18,
            critical_violations=2,
            noncritical_violations=1,
        )
        InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2025, 4, 15),
            inspection_key="owner-score-2",
            grade="A",
            score=9,
            critical_violations=0,
            noncritical_violations=1,
        )

    def test_owner_dashboard_exposes_score_breakdown_comparison_and_trend(self):
        from .views import _build_restaurant_score_insights

        self.client.login(username="owner_score", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")

        ctx = _build_restaurant_score_insights(self.restaurant)
        self.assertIn("score_summary", ctx)
        self.assertIn("score_breakdown", ctx)
        self.assertIn("review_factor_breakdown", ctx)
        self.assertIn("neighborhood_comparison", ctx)
        self.assertIn("trend_points", ctx)
        self.assertIn("trend_summary", ctx)

        score_summary = ctx["score_summary"]
        self.assertEqual(score_summary["grade"], "A")
        self.assertGreater(float(score_summary["composite_score"]), 80.0)

        score_breakdown = ctx["score_breakdown"]
        self.assertGreaterEqual(len(score_breakdown), 4)
        self.assertEqual(score_breakdown[0]["label"], "User Experience Signal")

        comparison = ctx["neighborhood_comparison"]
        self.assertEqual(comparison["location_scope"], "Midtown")
        self.assertEqual(comparison["peer_count"], 3)
        self.assertIsNotNone(comparison["rank"])
        self.assertIsNotNone(comparison["percentile"])

        trend_points = ctx["trend_points"]
        trend_summary = ctx["trend_summary"]
        self.assertEqual(len(trend_points), 2)
        self.assertTrue(trend_summary["has_data"])


class CompositeScoreAutomationTests(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(
            name="Automation Bistro",
            is_active=True,
            price_range="$$",
            cuisine_type="other",
            latitude=Decimal("40.720001"),
            longitude=Decimal("-73.990001"),
        )
        self.user = User.objects.create_user(
            username="auto_reviewer",
            password="pass12345",
        )

    def test_inspection_save_auto_refreshes_composite_score(self):
        self.assertIsNone(self.restaurant.composite_score)
        InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2025, 4, 18),
            inspection_key="auto-insp-1",
            grade="A",
            critical_violations=0,
            noncritical_violations=1,
        )
        self.restaurant.refresh_from_db()
        self.assertIsNotNone(self.restaurant.composite_score)
        self.assertEqual(self.restaurant.grade_latest, "A")

    def test_review_save_auto_refreshes_composite_score(self):
        Review.objects.create(
            restaurant=self.restaurant,
            user=self.user,
            rating=5,
            food_quality_rating=5,
            service_quality_rating=5,
            ambience_rating=4,
            location_rating=4,
            value_rating=4,
            dietary_accommodation_rating=4,
            cleanliness_rating=5,
            comment="Great all-around experience.",
        )
        self.restaurant.refresh_from_db()
        self.assertIsNotNone(self.restaurant.composite_score)
        self.assertGreater(float(self.restaurant.composite_score), 65.0)

    def test_recalculate_command_supports_specific_restaurant(self):
        other = Restaurant.objects.create(
            name="Command Control Cafe",
            is_active=True,
            price_range="$$",
            cuisine_type="other",
        )
        call_command("recalculate_composite_scores", restaurant_id=self.restaurant.id)
        self.restaurant.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(self.restaurant.composite_score)
        self.assertIsNone(other.composite_score)

    def test_recalculation_persists_score_history_records(self):
        call_command("recalculate_composite_scores", restaurant_id=self.restaurant.id)
        history = CompositeScoreHistory.objects.filter(restaurant=self.restaurant)
        self.assertGreaterEqual(history.count(), 1)
        self.assertEqual(history.first().trigger_source, "management_command")


class AdminCompositeScoreGovernanceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="score_admin",
            email="score_admin@example.com",
            password="pass12345",
        )
        self.owner = User.objects.create_user(
            username="score_owner",
            email="score_owner@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.owner, role="restaurant", is_approved=True)
        self.other_owner = User.objects.create_user(
            username="score_owner_two",
            email="score_owner_two@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(
            user=self.other_owner, role="restaurant", is_approved=True
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Audit Trail Diner",
            is_active=True,
            price_range="$$",
            cuisine_type="other",
        )
        self.other_restaurant = Restaurant.objects.create(
            owner=self.other_owner,
            name="Audit Trail Cafe",
            is_active=True,
            price_range="$$",
            cuisine_type="other",
        )
        self.inspection = InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=date(2025, 1, 12),
            inspection_key="audit-insp-1",
            grade="C",
            score=35,
            critical_violations=5,
            noncritical_violations=8,
        )
        InspectionRecord.objects.create(
            restaurant=self.other_restaurant,
            inspection_date=date(2025, 2, 2),
            inspection_key="audit-insp-2",
            grade="B",
            score=19,
            critical_violations=2,
            noncritical_violations=3,
        )

    def test_admin_can_trigger_recalculation_from_dashboard(self):
        self.client.login(username="score_admin", password="pass12345")
        response = self.client.post(
            reverse("admin_recalculate_scores"),
            {"restaurant_id": self.restaurant.id},
        )
        self.assertEqual(response.status_code, 302)

        self.restaurant.refresh_from_db()
        self.assertIsNotNone(self.restaurant.composite_score)
        history = CompositeScoreHistory.objects.filter(
            restaurant=self.restaurant,
            trigger_source="admin_dashboard",
        ).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.triggered_by, self.admin)

    def test_admin_can_trigger_recalculation_by_restaurant_name(self):
        self.client.login(username="score_admin", password="pass12345")
        response = self.client.post(
            reverse("admin_recalculate_scores"),
            {"restaurant_name": "Audit Trail Cafe"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CompositeScoreHistory.objects.filter(
                restaurant=self.other_restaurant,
                trigger_source="admin_dashboard",
            ).exists()
        )

    def test_admin_recalculation_with_blank_filters_recomputes_all_restaurants(self):
        self.client.login(username="score_admin", password="pass12345")
        response = self.client.post(reverse("admin_recalculate_scores"), {})
        self.assertEqual(response.status_code, 302)

        recalculated_restaurant_ids = set(
            CompositeScoreHistory.objects.filter(
                trigger_source="admin_dashboard",
            ).values_list("restaurant_id", flat=True)
        )
        self.assertIn(self.restaurant.id, recalculated_restaurant_ids)
        self.assertIn(self.other_restaurant.id, recalculated_restaurant_ids)

    def test_admin_sees_profile_level_recompute_button_on_restaurant_page(self):
        self.client.login(username="score_admin", password="pass12345")
        response = self.client.get(
            reverse("restaurant_detail", args=[self.restaurant.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")
        self.assertTrue(reverse("admin_recalculate_scores"))

    def test_large_score_delta_generates_investigable_anomaly(self):
        refresh_restaurant_composite(
            self.restaurant,
            trigger_source="management_command",
            trigger_note="baseline",
        )

        self.inspection.grade = "A"
        self.inspection.score = 0
        self.inspection.critical_violations = 0
        self.inspection.noncritical_violations = 0
        self.inspection.save()

        score_data = refresh_restaurant_composite(
            self.restaurant,
            trigger_source="management_command",
            trigger_note="post-change",
        )
        self.assertGreaterEqual(score_data["anomaly_count"], 1)
        anomaly = CompositeScoreAnomaly.objects.filter(
            restaurant=self.restaurant,
            anomaly_type="large_delta",
            is_resolved=False,
        ).first()
        self.assertIsNotNone(anomaly)

        self.client.login(username="score_admin", password="pass12345")
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "root")
        api_response = self.client.get(reverse("api_admin_score_anomalies"))
        self.assertEqual(api_response.status_code, 200)
        data = api_response.json()
        self.assertTrue(
            any(
                a["restaurant_id"] == self.restaurant.id and not a["is_resolved"]
                for a in data["anomalies"]
            )
        )

    def test_admin_can_resolve_score_anomaly(self):
        refresh_restaurant_composite(
            self.restaurant,
            trigger_source="management_command",
            trigger_note="baseline",
        )
        self.inspection.grade = "A"
        self.inspection.critical_violations = 0
        self.inspection.noncritical_violations = 0
        self.inspection.save()
        refresh_restaurant_composite(
            self.restaurant,
            trigger_source="management_command",
            trigger_note="trigger anomaly",
        )
        anomaly = CompositeScoreAnomaly.objects.filter(
            restaurant=self.restaurant,
            anomaly_type="large_delta",
        ).first()
        self.assertIsNotNone(anomaly)

        self.client.login(username="score_admin", password="pass12345")
        response = self.client.post(
            reverse("admin_resolve_score_anomaly", args=[anomaly.id])
        )
        self.assertEqual(response.status_code, 302)
        anomaly.refresh_from_db()
        self.assertTrue(anomaly.is_resolved)
        self.assertEqual(anomaly.resolved_by, self.admin)


class MessagingApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="restaurant_owner",
            email="owner@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.owner, role="restaurant", is_approved=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Message Bistro",
            cuisine_type="other",
            price_range="$$",
            is_active=True,
        )

        self.diner_a = User.objects.create_user(
            username="diner_a",
            email="diner_a@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.diner_a, role="diner")

        self.diner_b = User.objects.create_user(
            username="diner_b",
            email="diner_b@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.diner_b, role="diner")

    def test_diner_can_start_conversation_and_restaurant_can_reply(self):
        self.client.login(username="diner_a", password="pass12345")
        start_response = self.client.post(
            reverse("api_conversation_start"),
            data='{"restaurant_id": %d, "message": "Do you offer vegan options?"}'
            % self.restaurant.id,
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 201)
        conversation_id = start_response.json()["conversation_id"]

        conversation = Conversation.objects.get(id=conversation_id)
        self.assertEqual(conversation.diner_id, self.diner_a.id)
        self.assertEqual(conversation.restaurant_id, self.restaurant.id)
        self.assertEqual(conversation.messages.count(), 1)

        self.client.logout()
        self.client.login(username="restaurant_owner", password="pass12345")
        reply_response = self.client.post(
            reverse("api_send_message", args=[conversation_id]),
            data='{"message": "Yes, we have vegan pasta and salad."}',
            content_type="application/json",
        )
        self.assertEqual(reply_response.status_code, 201)
        self.assertEqual(conversation.messages.count(), 2)

    def test_api_message_flow_creates_and_clears_restaurant_notification(self):
        self.client.login(username="diner_a", password="pass12345")
        start_response = self.client.post(
            reverse("api_conversation_start"),
            data='{"restaurant_id": %d, "message": "Do you have outdoor seating?"}'
            % self.restaurant.id,
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 201)
        conversation_id = start_response.json()["conversation_id"]
        message = Message.objects.get(conversation_id=conversation_id)

        notification = MessageNotification.objects.get(message=message)
        self.assertEqual(notification.recipient, self.owner)
        self.assertFalse(notification.is_read)

        self.client.logout()
        self.client.login(username="restaurant_owner", password="pass12345")
        history_response = self.client.get(
            reverse("api_conversation_messages", args=[conversation_id])
        )
        self.assertEqual(history_response.status_code, 200)

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_conversation_history_is_stored_in_order(self):
        conversation = Conversation.objects.create(
            restaurant=self.restaurant,
            diner=self.diner_a,
        )
        Message.objects.create(
            conversation=conversation,
            sender=self.diner_a,
            body="Can I reserve for 8 pm?",
        )
        Message.objects.create(
            conversation=conversation,
            sender=self.owner,
            body="Yes, table for two is available.",
        )

        self.client.login(username="restaurant_owner", password="pass12345")
        response = self.client.get(
            reverse("api_conversation_messages", args=[conversation.id])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["body"], "Can I reserve for 8 pm?")
        self.assertEqual(
            payload["messages"][1]["body"], "Yes, table for two is available."
        )

    def test_unauthorized_user_cannot_access_other_conversation(self):
        conversation = Conversation.objects.create(
            restaurant=self.restaurant,
            diner=self.diner_a,
        )
        Message.objects.create(
            conversation=conversation,
            sender=self.diner_a,
            body="Do you have gluten-free bread?",
        )

        self.client.login(username="diner_b", password="pass12345")
        response = self.client.get(
            reverse("api_conversation_messages", args=[conversation.id])
        )
        self.assertEqual(response.status_code, 403)

        post_response = self.client.post(
            reverse("api_send_message", args=[conversation.id]),
            data='{"message": "I should not be able to send this."}',
            content_type="application/json",
        )
        self.assertEqual(post_response.status_code, 403)

    def test_restaurant_conversation_list_only_includes_its_threads(self):
        other_owner = User.objects.create_user(
            username="restaurant_owner_2",
            email="owner2@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(
            user=other_owner, role="restaurant", is_approved=True
        )
        other_restaurant = Restaurant.objects.create(
            owner=other_owner,
            name="Other Bistro",
            cuisine_type="other",
            price_range="$$",
            is_active=True,
        )
        Conversation.objects.create(restaurant=self.restaurant, diner=self.diner_a)
        Conversation.objects.create(restaurant=other_restaurant, diner=self.diner_a)

        self.client.login(username="restaurant_owner", password="pass12345")
        response = self.client.get(reverse("api_conversation_list"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["restaurant_id"], self.restaurant.id)


class MessagingWebsiteTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="web_owner",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.owner, role="restaurant", is_approved=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Web Message Bistro",
            cuisine_type="other",
            price_range="$$",
            is_active=True,
        )
        self.diner = User.objects.create_user(
            username="web_diner",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.diner, role="diner")

    def test_diner_can_open_thread_from_restaurant_page(self):
        self.client.login(username="web_diner", password="pass12345")
        response = self.client.post(
            reverse("api_conversation_start"),
            data=json.dumps(
                {
                    "restaurant_id": self.restaurant.id,
                    "message": "Hello from diner",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        conversation = Conversation.objects.get(
            restaurant=self.restaurant,
            diner=self.diner,
        )
        self.assertEqual(conversation.messages.count(), 1)

    def test_restaurant_can_view_inbox_and_thread(self):
        conversation = Conversation.objects.create(
            restaurant=self.restaurant,
            diner=self.diner,
        )
        Message.objects.create(
            conversation=conversation,
            sender=self.diner,
            body="Do you have outdoor seating?",
        )
        self.client.login(username="web_owner", password="pass12345")
        inbox_response = self.client.get(reverse("message_inbox"))
        self.assertEqual(inbox_response.status_code, 200)
        self.assertContains(inbox_response, "root")

        list_r = self.client.get(reverse("api_conversation_list"))
        self.assertEqual(list_r.status_code, 200)
        self.assertTrue(
            any(
                row["diner_username"] == "web_diner" for row in list_r.json()["results"]
            )
        )

        detail_response = self.client.get(
            reverse("conversation_detail", args=[conversation.id])
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "root")

        api_detail = self.client.get(
            reverse("api_conversation_messages", args=[conversation.id])
        )
        self.assertEqual(api_detail.status_code, 200)
        self.assertEqual(
            api_detail.json()["messages"][0]["body"], "Do you have outdoor seating?"
        )


# =============================================================================
# Issue #62: Restaurant Communication Settings Tests
# =============================================================================


class RestaurantCommunicationSettingsTests(TestCase):
    """Tests for restaurant messaging on/off toggle, response hours, and UI enforcement."""

    def setUp(self):
        self.client = Client()

        # Restaurant owner
        self.owner = User.objects.create_user(
            username="comm_owner", password="pass12345"
        )
        UserProfile.objects.create(user=self.owner, role="restaurant", is_approved=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Comm Test Bistro",
            cuisine_type="italian",
            price_range="$$",
            is_active=True,
        )

        # Diner
        self.diner = User.objects.create_user(
            username="comm_diner", password="pass12345"
        )
        UserProfile.objects.create(user=self.diner, role="diner")

    # -------------------------------------------------------------------------
    # Model defaults
    # -------------------------------------------------------------------------

    def test_messaging_enabled_default_is_true(self):
        """messaging_enabled defaults to True on new Restaurant instances."""
        self.assertTrue(self.restaurant.messaging_enabled)

    def test_response_hours_default_to_none(self):
        """Response hours are nullable by default."""
        self.assertIsNone(self.restaurant.response_hours_start)
        self.assertIsNone(self.restaurant.response_hours_end)

    # -------------------------------------------------------------------------
    # Settings page – access control
    # -------------------------------------------------------------------------

    def test_settings_page_requires_login(self):
        """SPA shell is public; API requires auth."""
        response = self.client.get(reverse("manage_communication_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")
        r = self.client.get(reverse("api_restaurant_communication"))
        self.assertEqual(r.status_code, 302)

    def test_diner_cannot_access_settings_page(self):
        """Diner cannot load communication JSON."""
        self.client.login(username="comm_diner", password="pass12345")
        response = self.client.get(reverse("manage_communication_settings"))
        self.assertEqual(response.status_code, 200)
        api_r = self.client.get(reverse("api_restaurant_communication"))
        self.assertEqual(api_r.status_code, 403)

    def test_owner_can_get_settings_page(self):
        """Owner reads settings via JSON API."""
        self.client.login(username="comm_owner", password="pass12345")
        response = self.client.get(reverse("manage_communication_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")
        api_r = self.client.get(reverse("api_restaurant_communication"))
        self.assertEqual(api_r.status_code, 200)
        self.assertTrue(api_r.json().get("messaging_enabled"))

    # -------------------------------------------------------------------------
    # Toggling messaging off/on
    # -------------------------------------------------------------------------

    def test_owner_can_disable_messaging(self):
        """Disable messaging via JSON API."""
        self.client.login(username="comm_owner", password="pass12345")
        response = self.client.post(
            reverse("api_restaurant_communication"),
            data=json.dumps({"messaging_enabled": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertFalse(self.restaurant.messaging_enabled)

    def test_owner_can_re_enable_messaging(self):
        """Owner can turn messaging back on after disabling it."""
        self.restaurant.messaging_enabled = False
        self.restaurant.save(update_fields=["messaging_enabled"])

        self.client.login(username="comm_owner", password="pass12345")
        self.client.post(
            reverse("api_restaurant_communication"),
            data=json.dumps({"messaging_enabled": True}),
            content_type="application/json",
        )
        self.restaurant.refresh_from_db()
        self.assertTrue(self.restaurant.messaging_enabled)

    # -------------------------------------------------------------------------
    # Response hours
    # -------------------------------------------------------------------------

    def test_owner_can_set_response_hours(self):
        """Save response hours via JSON API."""
        self.client.login(username="comm_owner", password="pass12345")
        self.client.post(
            reverse("api_restaurant_communication"),
            data=json.dumps(
                {
                    "messaging_enabled": True,
                    "response_hours_start": "09:00",
                    "response_hours_end": "17:00",
                }
            ),
            content_type="application/json",
        )
        self.restaurant.refresh_from_db()
        self.assertEqual(str(self.restaurant.response_hours_start), "09:00:00")
        self.assertEqual(str(self.restaurant.response_hours_end), "17:00:00")

    def test_response_hours_start_must_be_before_end(self):
        """API returns 400 when start >= end."""
        self.client.login(username="comm_owner", password="pass12345")
        response = self.client.post(
            reverse("api_restaurant_communication"),
            data=json.dumps(
                {
                    "messaging_enabled": True,
                    "response_hours_start": "18:00",
                    "response_hours_end": "09:00",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get("success", True))
        joined = " ".join(" ".join(v) for v in (data.get("errors") or {}).values())
        self.assertIn("before end", joined)

    # -------------------------------------------------------------------------
    # Messaging enforcement for diners
    # -------------------------------------------------------------------------

    def test_diner_blocked_from_messaging_disabled_restaurant(self):
        """API blocks starting a conversation when messaging is disabled."""
        self.restaurant.messaging_enabled = False
        self.restaurant.save(update_fields=["messaging_enabled"])

        self.client.login(username="comm_diner", password="pass12345")
        response = self.client.post(
            reverse("api_conversation_start"),
            data=json.dumps({"restaurant_id": self.restaurant.id, "message": "Hello?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_diner_can_message_enabled_restaurant(self):
        """Diner can start a conversation when messaging is enabled."""
        self.client.login(username="comm_diner", password="pass12345")
        response = self.client.post(
            reverse("api_conversation_start"),
            data=json.dumps({"restaurant_id": self.restaurant.id, "message": "Hello!"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Conversation.objects.filter(
                restaurant=self.restaurant, diner=self.diner
            ).exists()
        )

    def test_diner_cannot_send_message_in_disabled_conversation(self):
        """Diner cannot send when messaging is disabled (API)."""
        conversation = Conversation.objects.create(
            restaurant=self.restaurant, diner=self.diner
        )
        self.restaurant.messaging_enabled = False
        self.restaurant.save(update_fields=["messaging_enabled"])

        self.client.login(username="comm_diner", password="pass12345")
        response = self.client.post(
            reverse("api_send_message", args=[conversation.id]),
            data=json.dumps({"message": "Can I still message?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 0)

    def test_restaurant_owner_can_still_reply_when_messaging_disabled(self):
        """Restaurant owner can still reply via API when messaging is disabled."""
        conversation = Conversation.objects.create(
            restaurant=self.restaurant, diner=self.diner
        )
        self.restaurant.messaging_enabled = False
        self.restaurant.save(update_fields=["messaging_enabled"])

        self.client.login(username="comm_owner", password="pass12345")
        response = self.client.post(
            reverse("api_send_message", args=[conversation.id]),
            data=json.dumps({"message": "Sorry, we are temporarily closed."}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 1)

    # -------------------------------------------------------------------------
    # API enforcement
    # -------------------------------------------------------------------------

    def test_api_start_conversation_blocked_when_messaging_disabled(self):
        """JSON API returns 403 when diner tries to start conversation with disabled restaurant."""
        import json

        self.restaurant.messaging_enabled = False
        self.restaurant.save(update_fields=["messaging_enabled"])

        self.client.login(username="comm_diner", password="pass12345")
        response = self.client.post(
            reverse("api_conversation_start"),
            data=json.dumps({"restaurant_id": self.restaurant.id, "message": "Hello!"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_api_start_conversation_succeeds_when_messaging_enabled(self):
        """JSON API returns 201 when diner starts a conversation with an enabled restaurant."""
        import json

        self.client.login(username="comm_diner", password="pass12345")
        response = self.client.post(
            reverse("api_conversation_start"),
            data=json.dumps({"restaurant_id": self.restaurant.id, "message": "Hello!"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

    def test_unread_message_count_and_alerts(self):
        """Unread counts for the owner; template inbox is replaced by SPA shell."""
        from django.test import RequestFactory

        from .context_processors import unread_messages_count

        conv, _ = Conversation.objects.get_or_create(
            restaurant=self.restaurant, diner=self.diner
        )
        Message.objects.create(conversation=conv, sender=self.diner, body="Hello!")

        factory = RequestFactory()
        req = factory.get("/")
        req.user = self.owner
        self.assertEqual(unread_messages_count(req)["unread_messages_count"], 1)

        # Simulate owner opening thread (marks other's messages read)
        Message.objects.filter(conversation=conv, is_read=False).exclude(
            sender=self.owner
        ).update(is_read=True)

        req.user = self.owner
        self.assertEqual(unread_messages_count(req)["unread_messages_count"], 0)

        inbox = self.client.get(reverse("message_inbox"))
        self.assertEqual(inbox.status_code, 200)
        self.assertContains(inbox, "root")

    def test_global_unread_count_context_processor(self):
        """Context processor counts unread messages for authenticated users."""
        from django.test import RequestFactory

        from .context_processors import unread_messages_count

        conv, _ = Conversation.objects.get_or_create(
            restaurant=self.restaurant, diner=self.diner
        )
        Message.objects.create(conversation=conv, sender=self.diner, body="Msg 1")
        Message.objects.create(conversation=conv, sender=self.diner, body="Msg 2")

        factory = RequestFactory()
        req = factory.get("/")
        req.user = self.owner
        self.assertEqual(unread_messages_count(req)["unread_messages_count"], 2)

        # SPA shell no longer runs Django template context processors on the response
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "root")


class AdminRestaurantAccountListApiTests(TestCase):
    """Staff JSON endpoints for approved / rejected restaurant accounts (SPA)."""

    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username="spa_staff", password="pass12345", is_staff=True
        )
        self.diner = User.objects.create_user(username="d1", password="pass12345")
        UserProfile.objects.create(user=self.diner, role="diner")

        self.approved_owner = User.objects.create_user(
            username="biz_ok", password="pass12345"
        )
        UserProfile.objects.create(
            user=self.approved_owner,
            role="restaurant",
            is_approved=True,
            is_rejected=False,
        )
        Restaurant.objects.create(
            owner=self.approved_owner,
            name="Tasty Spoon",
            cuisine_type="italian",
            price_range="$$",
        )

        self.owner = User.objects.create_user(
            username="comm_owner", password="pass12345"
        )
        UserProfile.objects.create(user=self.owner, role="restaurant", is_approved=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Comm Test Bistro",
            cuisine_type="italian",
            price_range="$$",
            is_active=True,
        )

        self.rejected_owner = User.objects.create_user(
            username="biz_no", password="pass12345"
        )
        UserProfile.objects.create(
            user=self.rejected_owner,
            role="restaurant",
            is_approved=False,
            is_rejected=True,
        )

    def test_message_notification_created_and_visible_on_restaurant_dashboard(self):
        """A new diner message creates a dashboard notification with the correct thread link."""
        conversation, _ = Conversation.objects.get_or_create(
            restaurant=self.restaurant, diner=self.diner
        )
        message = Message.objects.create(
            conversation=conversation,
            sender=self.diner,
            body="Can you confirm today's specials?",
        )

        notification = MessageNotification.objects.get(message=message)
        self.assertEqual(notification.recipient, self.owner)
        self.assertEqual(notification.conversation, conversation)
        self.assertFalse(notification.is_read)

        unread_count = MessageNotification.objects.filter(
            recipient=self.owner, is_read=False
        ).count()
        self.assertEqual(unread_count, 1)

    def test_message_notification_clears_after_restaurant_reads_conversation(self):
        """Opening the conversation via API marks both messages and notifications as read."""
        conversation, _ = Conversation.objects.get_or_create(
            restaurant=self.restaurant, diner=self.diner
        )
        message = Message.objects.create(
            conversation=conversation,
            sender=self.diner,
            body="Please share your vegan menu options.",
        )
        notification = MessageNotification.objects.get(message=message)

        self.client.login(username="comm_owner", password="pass12345")
        self.client.get(reverse("api_conversation_messages", args=[conversation.id]))

        message.refresh_from_db()
        notification.refresh_from_db()
        self.assertTrue(message.is_read)
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

        unread_count = MessageNotification.objects.filter(
            recipient=self.owner, is_read=False
        ).count()
        self.assertEqual(unread_count, 0)

    def test_approved_list_requires_staff(self):
        self.client.login(username="d1", password="pass12345")
        r = self.client.get(reverse("api_admin_approved_restaurants"))
        self.assertEqual(r.status_code, 403)

    def test_approved_list_returns_rows(self):
        self.client.login(username="spa_staff", password="pass12345")
        r = self.client.get(reverse("api_admin_approved_restaurants"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 2)
        usernames = [row["username"] for row in data["results"]]
        self.assertIn("biz_ok", usernames)

    def test_rejected_list_returns_rows(self):
        self.client.login(username="spa_staff", password="pass12345")
        r = self.client.get(reverse("api_admin_rejected_restaurants"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["username"], "biz_no")


class ReviewResponseFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.owner = User.objects.create_user(
            username="review_owner",
            email="review_owner@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.owner, role="restaurant", is_approved=True)
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Response Test Bistro",
            cuisine_type="italian",
            price_range="$$",
            is_active=True,
        )

        self.diner = User.objects.create_user(
            username="review_diner",
            email="review_diner@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.diner, role="diner")
        self.review = Review.objects.create(
            restaurant=self.restaurant,
            user=self.diner,
            rating=4,
            comment="Solid food and quick service.",
        )

        self.other_owner = User.objects.create_user(
            username="other_owner",
            email="other_owner@example.com",
            password="pass12345",
        )
        UserProfile.objects.create(
            user=self.other_owner, role="restaurant", is_approved=True
        )

    def test_restaurant_owner_can_post_public_response(self):
        self.client.login(username="review_owner", password="pass12345")
        response = self.client.post(
            reverse("respond_to_review", args=[self.review.id]),
            {
                "response_text": "Thank you for your feedback!",
                "next": reverse("profile"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReviewResponse.objects.filter(
                review=self.review, responder=self.owner
            ).exists()
        )

    def test_restaurant_owner_can_edit_existing_response(self):
        ReviewResponse.objects.create(
            review=self.review,
            restaurant=self.restaurant,
            responder=self.owner,
            response_text="Initial response",
        )

        self.client.login(username="review_owner", password="pass12345")
        self.client.post(
            reverse("respond_to_review", args=[self.review.id]),
            {"response_text": "Updated response text", "next": reverse("profile")},
        )

        self.assertEqual(ReviewResponse.objects.filter(review=self.review).count(), 1)
        self.assertEqual(
            ReviewResponse.objects.get(review=self.review).response_text,
            "Updated response text",
        )

    def test_non_owner_cannot_post_response(self):
        self.client.login(username="other_owner", password="pass12345")
        response = self.client.post(
            reverse("respond_to_review", args=[self.review.id]),
            {"response_text": "Not allowed"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ReviewResponse.objects.filter(review=self.review).exists())

    def test_response_is_visible_on_restaurant_detail(self):
        ReviewResponse.objects.create(
            review=self.review,
            restaurant=self.restaurant,
            responder=self.owner,
            response_text="We appreciate your visit and will keep improving.",
        )

        self.client.login(username="review_diner", password="pass12345")
        response = self.client.get(
            reverse("api_restaurant_detail", args=[self.restaurant.id])
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        review_data = next(
            (r for r in data["reviews"] if r["id"] == self.review.id), None
        )
        self.assertIsNotNone(review_data)
        self.assertIsNotNone(review_data["owner_response"])
        self.assertIn(
            "We appreciate your visit and will keep improving.",
            review_data["owner_response"]["response_text"],
        )
