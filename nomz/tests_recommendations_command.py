from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from nomz.models import (
    RecalculatedRecommendation,
    RecommendationModelMetric,
    Restaurant,
    UserInteractionHistory,
    UserPreference,
)


class RecalculateRecommendationsCommandTests(TestCase):
    def test_recalculate_recommendations_command_processes_seed_data(self):
        # Required dataset shape from request: >=3 restaurants and >=2 users.
        restaurants = [
            Restaurant.objects.create(
                name=f"Command Rec Spot {idx}",
                cuisine_type="other",
                price_range="$$",
                is_active=True,
                composite_score=Decimal("80.00") - idx,
            )
            for idx in range(1, 4)
        ]

        user1 = User.objects.create_user(username="rec_user_1", password="pass12345")
        user2 = User.objects.create_user(username="rec_user_2", password="pass12345")
        prefs1 = UserPreference.objects.create(
            user=user1,
            favorite_cuisines=["thai"],
            dietary_restrictions=[],
            neighborhood_preference="",
            price_preference="$$",
            minimum_interactions_for_learning=3,
        )
        UserPreference.objects.create(
            user=user2,
            favorite_cuisines=["italian"],
            dietary_restrictions=[],
            neighborhood_preference="",
            price_preference="$$",
            minimum_interactions_for_learning=3,
        )

        # Give user1 enough interaction history so recalculation path executes.
        for _ in range(3):
            UserInteractionHistory.objects.create(
                user=user1,
                restaurant=restaurants[0],
                interaction_type="view",
            )

        # Seed today's recommendation rows so metrics table has data to update.
        RecalculatedRecommendation.objects.create(
            user=user1,
            restaurant=restaurants[0],
            recommendation_score=Decimal("88.00"),
            cuisine_score=Decimal("8.00"),
            price_score=Decimal("7.00"),
            dietary_score=Decimal("6.00"),
            user_interacted=True,
            days_to_interaction=1,
        )
        RecalculatedRecommendation.objects.create(
            user=user2,
            restaurant=restaurants[1],
            recommendation_score=Decimal("70.00"),
            cuisine_score=Decimal("5.00"),
            price_score=Decimal("5.00"),
            dietary_score=Decimal("5.00"),
            user_interacted=False,
        )

        stdout = StringIO()
        call_command("recalculate_recommendations", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Successfully recalculated recommendations for", output)
        self.assertIn("Daily metrics calculated:", output)

        metric = RecommendationModelMetric.objects.filter(
            metric_date=timezone.now().date()
        ).first()
        self.assertIsNotNone(metric)
        self.assertEqual(metric.total_recommendations_given, 2)
        self.assertEqual(metric.total_users_with_recommendations, 2)
        self.assertEqual(metric.successful_recommendations, 1)

        # Command should have touched recommendation-learning state for eligible users.
        prefs1.refresh_from_db()
        self.assertGreaterEqual(prefs1.recommendation_model_version, 2)
