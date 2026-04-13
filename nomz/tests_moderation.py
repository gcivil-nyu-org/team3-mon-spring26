import json

from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import ModerationReport, Restaurant, Review, SystemAuditLog, UserProfile


class ModerationTests(TestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_superuser(
            username="admin", password="password", email="admin@test.com"
        )
        self.diner_user = User.objects.create_user(
            username="diner", password="password"
        )
        self.reporter_user = User.objects.create_user(
            username="reporter", password="password"
        )

        # Create UserProfiles
        UserProfile.objects.create(user=self.admin_user, role="admin")
        UserProfile.objects.create(user=self.diner_user, role="diner")
        UserProfile.objects.create(user=self.reporter_user, role="diner")

        # Create a restaurant
        self.restaurant = Restaurant.objects.create(
            name="Test Cafe",
            address="123 Test St",
            cuisine="Test",
            owner=self.admin_user,
        )

        self.client = Client()

    def test_add_review(self):
        self.client.login(username="diner", password="password")
        url = reverse("api_restaurant_add_review", args=[self.restaurant.id])
        response = self.client.post(
            url,
            json.dumps(
                {
                    "rating": 5,
                    "food_quality_rating": 5,
                    "service_quality_rating": 4,
                    "ambience_rating": 4,
                    "location_rating": 5,
                    "value_rating": 4,
                    "dietary_accommodation_rating": 4,
                    "cleanliness_rating": 5,
                    "comment": "Great place!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.comment, "Great place!")
        self.assertEqual(review.user, self.diner_user)
        self.assertEqual(review.food_quality_rating, 5)

        self.restaurant.refresh_from_db()
        self.assertIsNotNone(self.restaurant.composite_score)
        self.assertIsNotNone(self.restaurant.composite_score_calculated_at)

    def test_report_review(self):
        # Create a review first
        review = Review.objects.create(
            restaurant=self.restaurant,
            user=self.diner_user,
            rating=1,
            comment="Bad service!",
        )

        self.client.login(username="reporter", password="password")
        url = reverse("api_report_content")
        response = self.client.post(
            url,
            json.dumps(
                {
                    "content_type": "review",
                    "content_id": review.id,
                    "reason": "HARASSMENT",
                    "details": "Abusive language",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ModerationReport.objects.count(), 1)
        report = ModerationReport.objects.first()
        self.assertEqual(report.review, review)
        self.assertEqual(report.reason, "HARASSMENT")
        self.assertEqual(report.status, "PENDING")

    def test_admin_resolve_report_delete(self):
        # Create a review and a report
        review = Review.objects.create(
            restaurant=self.restaurant,
            user=self.diner_user,
            rating=1,
            comment="Spam review",
        )
        report = ModerationReport.objects.create(
            reporter=self.reporter_user, review=review, reason="SPAM"
        )

        self.client.login(username="admin", password="password")
        url = reverse("api_admin_resolve_report_api", args=[report.id])
        response = self.client.post(
            url,
            json.dumps(
                {"action": "delete", "moderator_note": "Confirmed spam"},
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Check report updated
        report.refresh_from_db()
        self.assertEqual(report.status, "RESOLVED")
        self.assertEqual(report.action_taken, "Review soft-deleted")

        # Check review updated
        review.refresh_from_db()
        self.assertTrue(review.is_deleted)
        self.restaurant.refresh_from_db()
        self.assertIsNotNone(self.restaurant.composite_score)

        # Check audit log
        self.assertEqual(
            SystemAuditLog.objects.filter(action="moderation_delete").count(), 1
        )

    def test_admin_resolve_report_dismiss(self):
        review = Review.objects.create(
            restaurant=self.restaurant, user=self.diner_user, rating=4, comment="Good"
        )
        report = ModerationReport.objects.create(
            reporter=self.reporter_user, review=review, reason="OTHER"
        )

        self.client.login(username="admin", password="password")
        url = reverse("api_admin_resolve_report_api", args=[report.id])
        self.client.post(
            url,
            json.dumps({"action": "dismiss", "moderator_note": "Valid review"}),
            content_type="application/json",
        )

        report.refresh_from_db()
        self.assertEqual(report.status, "DISMISSED")
        self.assertFalse(review.is_deleted)
        self.assertEqual(
            SystemAuditLog.objects.filter(action="moderation_dismiss").count(), 1
        )

    def test_admin_resolve_report_flag_user(self):
        # Report the restaurant owner
        report = ModerationReport.objects.create(
            reporter=self.reporter_user, reported_user=self.admin_user, reason="FRAUD"
        )

        self.client.login(username="admin", password="password")
        url = reverse("api_admin_resolve_report_api", args=[report.id])
        response = self.client.post(
            url,
            json.dumps(
                {"action": "flag_fraud", "moderator_note": "Confirmed fraud"},
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Check report updated
        report.refresh_from_db()
        self.assertEqual(report.status, "RESOLVED")
        self.assertEqual(
            report.action_taken, "User and associated restaurant(s) flagged for fraud"
        )

        # Check UserProfile is flagged
        user_profile = UserProfile.objects.get(user=self.admin_user)
        self.assertTrue(user_profile.is_flagged)

        # Check Restaurant is flagged
        self.restaurant.refresh_from_db()
        self.assertTrue(self.restaurant.is_flagged)
