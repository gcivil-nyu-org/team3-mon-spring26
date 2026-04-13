from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from nomz.models import (
    UserPreference,
    RecommendationModelMetric,
    RecalculatedRecommendation,
)
from nomz.signals import recalculate_user_recommendation_model
from django.db import models


class Command(BaseCommand):
    help = (
        "Recalculate recommendation models for all users based on interaction history"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Recalculate for specific user ID",
        )
        parser.add_argument(
            "--min-interactions",
            type=int,
            default=3,
            help="Minimum interactions required to trigger recalculation",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        min_interactions = options.get("min_interactions")

        if user_id:
            # Single user
            users = User.objects.filter(id=user_id)
        else:
            # All users with preferences
            users = User.objects.filter(preferences__isnull=False)

        updated_count = 0
        for user in users:
            if self._recalculate_for_user(user, min_interactions):
                updated_count += 1
            self.stdout.write(".")

        # Calculate and store daily metrics
        self._calculate_daily_metrics()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully recalculated recommendations for {updated_count} users"
            )
        )

    def _recalculate_for_user(self, user, min_interactions):
        """Recalculate recommendation model for a specific user"""
        try:
            prefs = user.preferences
        except UserPreference.DoesNotExist:
            return False

        if not prefs.has_enough_data_for_learning():
            return False

        # Trigger model recalculation
        recalculate_user_recommendation_model(user.id)

        return True

    def _calculate_daily_metrics(self):
        """Calculate and store daily recommendation metrics"""
        today = timezone.now().date()

        # Get all recommendations from today
        today_recs = RecalculatedRecommendation.objects.filter(
            calculated_at__date=today
        )

        if today_recs.count() == 0:
            self.stdout.write("No recommendations to calculate metrics for")
            return

        successful_recs = today_recs.filter(user_interacted=True).count()
        total_recs = today_recs.count()

        accuracy = (successful_recs / total_recs * 100) if total_recs > 0 else 0

        # Calculate average days to interaction
        recs_with_interaction = today_recs.filter(
            user_interacted=True,
            days_to_interaction__isnull=False,
        )

        if recs_with_interaction.exists():
            avg_days = recs_with_interaction.aggregate(
                avg=models.Avg("days_to_interaction")
            )["avg"]
        else:
            avg_days = None

        # Count unique users
        unique_users = today_recs.values("user_id").distinct().count()

        # Create or update metric
        RecommendationModelMetric.objects.update_or_create(
            metric_date=today,
            defaults={
                "total_recommendations_given": total_recs,
                "total_users_with_recommendations": unique_users,
                "successful_recommendations": successful_recs,
                "avg_recommendation_accuracy": Decimal(str(accuracy)),
                "avg_days_to_interaction": Decimal(str(avg_days)) if avg_days else None,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDaily metrics calculated: {accuracy:.1f}% accuracy "
                f"({successful_recs}/{total_recs} recommendations)"
            )
        )
