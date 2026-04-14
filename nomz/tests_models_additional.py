from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import (
    Conversation,
    FriendConversation,
    RecalculatedRecommendation,
    RecommendationModelMetric,
    Restaurant,
    RestaurantOwnershipClaim,
    Review,
    UserInteractionHistory,
    UserPreference,
)


class RestaurantOwnershipClaimModelTests(TestCase):
    def setUp(self):
        self.claimant = User.objects.create_user(
            username="claimant", password="pass12345"
        )
        self.other_owner = User.objects.create_user(
            username="existing_owner", password="pass12345"
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.other_owner,
            name="Claim Guard Restaurant",
            cuisine_type="other",
            price_range="$$",
        )

    def test_clean_rejects_claim_for_restaurant_owned_by_another_user(self):
        claim = RestaurantOwnershipClaim(
            claimant=self.claimant,
            restaurant=self.restaurant,
        )
        with self.assertRaises(ValidationError):
            claim.clean()

    def test_reject_updates_status_and_metadata(self):
        self.restaurant.owner = None
        self.restaurant.save(update_fields=["owner"])
        reviewer = User.objects.create_user(username="reviewer", password="pass12345")
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant,
            restaurant=self.restaurant,
        )

        rejected = claim.reject(reviewer=reviewer, notes="Insufficient proof")

        self.assertEqual(rejected.status, RestaurantOwnershipClaim.STATUS_REJECTED)
        self.assertEqual(rejected.reviewed_by, reviewer)
        self.assertEqual(rejected.review_notes, "Insufficient proof")
        self.assertIsNotNone(rejected.reviewed_at)


class UserPreferenceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pref_user", password="pass12345")
        self.preference = UserPreference.objects.create(user=self.user)

    def test_recommendation_success_rate_handles_zero_and_non_zero_totals(self):
        self.assertEqual(self.preference.recommendation_success_rate, 0.0)
        self.preference.total_recommendations_received = 8
        self.preference.successful_recommendations = 3
        self.assertEqual(self.preference.recommendation_success_rate, 37.5)

    def test_all_weights_sum_and_reset_learning_weights(self):
        self.preference.cuisine_weight = Decimal("1.20")
        self.preference.dietary_weight = Decimal("1.10")
        self.preference.price_weight = Decimal("0.90")
        self.preference.neighborhood_weight = Decimal("1.30")
        self.preference.composite_score_weight = Decimal("0.80")
        self.preference.historical_satisfaction_weight = Decimal("0.70")
        self.assertEqual(self.preference.all_weights_sum, Decimal("6.00"))

        starting_version = self.preference.recommendation_model_version
        self.preference.reset_learning_weights()
        self.preference.refresh_from_db()

        self.assertEqual(self.preference.cuisine_weight, Decimal("1.0"))
        self.assertEqual(self.preference.historical_satisfaction_weight, Decimal("0.5"))
        self.assertEqual(
            self.preference.recommendation_model_version,
            starting_version + 1,
        )
        self.assertEqual(self.preference.learning_data_quality_score, Decimal("0.00"))

    def test_has_enough_data_for_learning_uses_minimum_interactions_threshold(self):
        self.preference.minimum_interactions_for_learning = 2
        self.preference.save(update_fields=["minimum_interactions_for_learning"])
        self.assertFalse(self.preference.has_enough_data_for_learning())

        UserInteractionHistory.objects.create(
            user=self.user,
            interaction_type="view",
        )
        UserInteractionHistory.objects.create(
            user=self.user,
            interaction_type="profile_view",
        )
        self.assertTrue(self.preference.has_enough_data_for_learning())


class RecommendationModelBehaviorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rec_user", password="pass12345")
        self.restaurant = Restaurant.objects.create(
            name="Recommendation Target",
            cuisine_type="other",
            price_range="$$",
        )

    def test_calculate_accuracy_from_interactions_uses_recent_review_branch(self):
        recommendation = RecalculatedRecommendation.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            recommendation_score=Decimal("88.00"),
        )
        recommendation.calculated_at = timezone.now() - timedelta(days=2)
        recommendation.save(update_fields=["calculated_at"])

        review = Review.objects.create(
            restaurant=self.restaurant,
            user=self.user,
            rating=5,
            comment="Excellent match",
        )
        recommendation.calculate_accuracy_from_interactions()
        recommendation.refresh_from_db()

        self.assertTrue(recommendation.user_interacted)
        self.assertEqual(recommendation.interaction_type, "review_submitted")
        self.assertEqual(recommendation.accuracy_feedback, 1)
        self.assertEqual(recommendation.interaction_detected_at, review.created_at)

    def test_calculate_accuracy_from_interactions_falls_back_to_view_branch(self):
        recommendation = RecalculatedRecommendation.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            recommendation_score=Decimal("65.00"),
        )
        recommendation.calculated_at = timezone.now() - timedelta(days=3)
        recommendation.save(update_fields=["calculated_at"])

        interaction = UserInteractionHistory.objects.create(
            user=self.user,
            restaurant=self.restaurant,
            interaction_type="view",
            created_at=timezone.now() - timedelta(days=1),
        )
        recommendation.calculate_accuracy_from_interactions()
        recommendation.refresh_from_db()

        self.assertTrue(recommendation.user_interacted)
        self.assertEqual(recommendation.interaction_type, "view")
        self.assertEqual(recommendation.accuracy_feedback, 0)
        self.assertEqual(recommendation.interaction_detected_at, interaction.created_at)

    def test_month_over_month_improvement_computes_delta(self):
        older = RecommendationModelMetric.objects.create(
            avg_recommendation_accuracy=Decimal("61.50")
        )
        older.metric_date = timezone.now().date() - timedelta(days=35)
        older.save(update_fields=["metric_date"])

        current = RecommendationModelMetric.objects.create(
            avg_recommendation_accuracy=Decimal("70.00")
        )
        self.assertEqual(current.month_over_month_improvement, 8.5)


class ConversationAccessModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass12345")
        self.diner = User.objects.create_user(username="diner", password="pass12345")
        self.other_user = User.objects.create_user(
            username="other", password="pass12345"
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Conversation Access Spot",
            cuisine_type="other",
            price_range="$$",
        )
        self.conversation = Conversation.objects.create(
            restaurant=self.restaurant,
            diner=self.diner,
        )

    def test_conversation_can_access_checks_auth_and_membership(self):
        self.assertTrue(self.conversation.can_access(self.owner))
        self.assertTrue(self.conversation.can_access(self.diner))
        self.assertFalse(self.conversation.can_access(self.other_user))
        self.assertFalse(self.conversation.can_access(AnonymousUser()))


class FriendConversationModelTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="friend_one", password="pass12345"
        )
        self.user2 = User.objects.create_user(
            username="friend_two", password="pass12345"
        )
        self.user3 = User.objects.create_user(
            username="friend_three", password="pass12345"
        )

    def test_get_participants_falls_back_to_legacy_user_fields(self):
        conversation = FriendConversation.objects.create(
            user1=self.user1, user2=self.user2
        )
        participants = set(conversation.get_participants().values_list("id", flat=True))
        self.assertEqual(participants, {self.user1.id, self.user2.id})

    def test_can_access_uses_participants_membership(self):
        conversation = FriendConversation.objects.create(is_group=True, name="Group")
        conversation.participants.add(self.user1, self.user2)

        self.assertTrue(conversation.can_access(self.user1))
        self.assertFalse(conversation.can_access(self.user3))
        self.assertFalse(conversation.can_access(AnonymousUser()))
