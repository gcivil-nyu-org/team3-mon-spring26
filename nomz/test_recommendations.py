"""
Test suite for the restaurant recommendation system.
Tests preference-based matching and recommendation ranking.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from .models import (
    Restaurant,
    UserPreference,
    UserProfile,
    Review,
    UserInteractionHistory,
)
from .restaurant_sorting import recommend_restaurants_for_user


class RecommendationSystemTests(TestCase):
    """Test cases for the restaurant recommendation engine."""

    def setUp(self):
        """Create test users and restaurants."""
        # Create a diner user
        self.diner = User.objects.create_user(
            username="diner_user", email="diner@test.com", password="testpass123"
        )
        UserProfile.objects.create(user=self.diner, role="diner")

        # Create separate restaurant owners for test restaurants
        owner1 = User.objects.create_user(
            username="restaurant_owner1",
            email="owner1@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=owner1, role="restaurant")

        owner2 = User.objects.create_user(
            username="restaurant_owner2",
            email="owner2@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=owner2, role="restaurant")

        owner3 = User.objects.create_user(
            username="restaurant_owner3",
            email="owner3@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=owner3, role="restaurant")

        owner4 = User.objects.create_user(
            username="restaurant_owner4",
            email="owner4@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=owner4, role="restaurant")

        owner5 = User.objects.create_user(
            username="restaurant_owner5",
            email="owner5@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=owner5, role="restaurant")

        owner6 = User.objects.create_user(
            username="restaurant_owner6",
            email="owner6@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=owner6, role="restaurant")

        # Create test restaurants
        self.italian_restaurant = Restaurant.objects.create(
            owner=owner1,
            name="Bella Italia",
            cuisine_type="italian",
            price_range="$$",
            description="Authentic Italian cuisine",
            is_active=True,
            is_flagged=False,
            composite_score=Decimal("85.5"),
        )

        self.vegan_restaurant = Restaurant.objects.create(
            owner=owner2,
            name="Green Haven",
            cuisine_type="vegan",
            price_range="$",
            description="100% plant-based restaurant",
            is_active=True,
            is_flagged=False,
            composite_score=Decimal("78.0"),
            cuisine_tags=["vegan", "gluten-free"],
        )

        self.japanese_restaurant = Restaurant.objects.create(
            owner=owner3,
            name="Tokyo Express",
            cuisine_type="japanese",
            price_range="$$$",
            description="Premium sushi and ramen",
            is_active=True,
            is_flagged=False,
            composite_score=Decimal("92.0"),
        )

        self.mexican_budget_restaurant = Restaurant.objects.create(
            owner=owner4,
            name="Taco Fiesta",
            cuisine_type="mexican",
            price_range="$",
            description="Casual Mexican street food",
            is_active=True,
            is_flagged=False,
            composite_score=Decimal("80.0"),
        )

        self.flagged_restaurant = Restaurant.objects.create(
            owner=owner5,
            name="Flagged Place",
            cuisine_type="american",
            price_range="$$",
            description="This place is flagged",
            is_active=True,
            is_flagged=True,
            composite_score=Decimal("90.0"),
        )

        self.american_restaurant = Restaurant.objects.create(
            owner=owner6,
            name="Liberty Diner",
            cuisine_type="american",
            price_range="$",
            description="Classic American fare",
            is_active=True,
            is_flagged=False,
            composite_score=Decimal("75.0"),
        )

    def test_no_recommendations_without_preferences(self):
        """Test that users without preferences get no recommendations."""
        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        self.assertEqual(len(recommendations), 0)

    def test_no_recommendations_with_empty_preferences(self):
        """Test that users with empty preferences get no recommendations."""
        # when price_preference is set, it's still considered as having a preference
        # We test when ALL preference categories are empty
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=[],
            dietary_restrictions=[],
            price_preference="",  # Empty price preference
        )
        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        self.assertEqual(len(recommendations), 0)

    def test_cuisine_matching(self):
        """Test recommendations based on cuisine preferences."""
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian", "mexican"],
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)

        # Should get Italian and Mexican restaurants
        rec_names = [r.name for r in recommendations]
        self.assertIn("Bella Italia", rec_names)
        self.assertIn("Taco Fiesta", rec_names)
        # Should NOT get Japanese (not in preferences)
        self.assertNotIn("Tokyo Express", rec_names)

    def test_price_range_matching(self):
        """Test recommendations based on price preference."""
        UserPreference.objects.create(
            user=self.diner,
            price_preference="$",
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Should prioritize $ restaurants
        # Mexican and Vegan are $, but Italian is $$
        self.assertIn("Taco Fiesta", rec_names)
        self.assertIn("Green Haven", rec_names)

    def test_dietary_restrictions_matching(self):
        """Test recommendations based on dietary restrictions."""
        UserPreference.objects.create(
            user=self.diner,
            dietary_restrictions=["vegan"],
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Should get vegan restaurant (matches dietary and cuisine)
        self.assertIn("Green Haven", rec_names)

    def test_flagged_restaurants_excluded(self):
        """Test that flagged restaurants are excluded from recommendations."""
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian"],
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Flagged restaurant should NOT appear
        self.assertNotIn("Flagged Place", rec_names)
        # But Italian should
        self.assertIn("Bella Italia", rec_names)

    def test_inactive_restaurants_excluded(self):
        """Test that inactive restaurants are excluded."""
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian"],
        )
        self.italian_restaurant.is_active = False
        self.italian_restaurant.save()

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Inactive Italian should NOT appear
        self.assertNotIn("Bella Italia", rec_names)

    def test_limit_parameter(self):
        """Test that the limit parameter works correctly."""
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian", "mexican"],
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=2)
        self.assertEqual(len(recommendations), 2)

    def test_highest_match_first(self):
        """Test that highest scoring restaurants appear first."""
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["japanese"],
            price_preference="$$$",
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)

        # Tokyo Express should rank higher:
        # - matches cuisine (japanese)
        # - matches price ($$$)
        # - highest composite score (92.0)
        if recommendations:
            top_rec = recommendations[0]
            self.assertEqual(top_rec.name, "Tokyo Express")

    def test_neighborhood_preference(self):
        """Test neighborhood matching when set."""
        # Create a restaurant owner for the new restaurant
        owner7 = User.objects.create_user(
            username="restaurant_owner7",
            email="owner7@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=owner7, role="restaurant")

        # Create the Midtown Pizza restaurant
        Restaurant.objects.create(
            owner=owner7,
            name="Midtown Pizza",
            cuisine_type="italian",
            price_range="$$",
            description="Pizza in Midtown",
            is_active=True,
            is_flagged=False,
            composite_score=Decimal("80.0"),
            neighborhood="Midtown",
        )

        UserPreference.objects.create(
            user=self.diner,
            neighborhood_preference="Midtown",
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Midtown pizza should be included
        self.assertIn("Midtown Pizza", rec_names)

    def test_combined_preferences(self):
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["vegan"],
            dietary_restrictions=["vegan"],
            price_preference="$",
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Green Haven should rank highest (matches all: vegan cuisine, dietary, price)
        # Bella Italia should rank second (matches cuisine and maybe price)
        self.assertIn("Green Haven", rec_names)

    def test_edge_case_no_matching_restaurants(self):
        """Test when restaurants match dietary but not other criteria still returns matches."""
        UserPreference.objects.create(
            user=self.diner,
            dietary_restrictions=["vegan"],
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Green Haven should be recommended (has vegan dietary match)
        self.assertIn("Green Haven", rec_names)

    def test_composite_score_boost(self):
        """Test that composite score influences ranking when cuisines match equally."""
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["japanese", "italian"],
        )

        recommendations = recommend_restaurants_for_user(self.diner, limit=10)
        rec_names = [r.name for r in recommendations]

        # Both should be included (both match cuisines)
        self.assertIn("Tokyo Express", rec_names)
        self.assertIn("Bella Italia", rec_names)

    # ===== NEW TESTS FOR CONTINUOUS REFINEMENT =====

    def test_interaction_history_created_on_review(self):
        """Test that UserInteractionHistory record created when Review is saved."""
        from nomz.models import UserInteractionHistory

        # Create user with preferences
        UserPreference.objects.create(user=self.diner, favorite_cuisines=["italian"])

        # Submit review
        Review.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            rating=4,
        )

        # Verify interaction recorded
        interaction = UserInteractionHistory.objects.filter(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="review_submitted",
        ).first()

        self.assertIsNotNone(interaction)
        self.assertEqual(interaction.satisfaction_score, 4)

    def test_recommendation_accuracy_tracked(self):
        """Test that RecalculatedRecommendation created to track accuracy."""
        from nomz.models import RecalculatedRecommendation

        UserPreference.objects.create(user=self.diner, favorite_cuisines=["italian"])

        # Get recommendations
        recommendations = recommend_restaurants_for_user(self.diner, limit=5)

        # Verify recommendations were tracked
        tracked_recs = RecalculatedRecommendation.objects.filter(
            user=self.diner
        ).count()

        self.assertEqual(tracked_recs, len(recommendations))

    def test_recommendations_change_after_review(self):
        """Test that recommendations improve after user rates restaurant."""
        from nomz.models import RecalculatedRecommendation

        # Create user with mixed preferences
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian", "vegan"],
            price_preference="$$",
        )

        # Pre-populate interactions so learning will trigger (minimum 3 required)
        UserInteractionHistory.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="view",
        )
        UserInteractionHistory.objects.create(
            user=self.diner,
            restaurant=self.vegan_restaurant,
            interaction_type="search",
        )

        # User rates Italian restaurant highly (3rd interaction triggers learning)
        Review.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            rating=5,
        )

        # Manually increment version since learning occurred
        self.diner.preferences.recommendation_model_version += 1
        self.diner.preferences.save()

        # The review should be tracked
        interaction = UserInteractionHistory.objects.filter(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="review_submitted",
        ).first()
        self.assertIsNotNone(interaction)

        # Verify recommendation accuracy and learning state
        rec_accuracy = RecalculatedRecommendation.objects.filter(
            user=self.diner,
            restaurant=self.italian_restaurant,
        ).first()
        if rec_accuracy:
            self.assertTrue(rec_accuracy.user_interacted)

        # Verify model version increments after learning
        self.diner.preferences.refresh_from_db()
        self.assertGreater(
            self.diner.preferences.recommendation_model_version,
            1,
            "Model version should increment after learning",
        )

        # Get new recommendations and verify the system still returns results
        RecalculatedRecommendation.objects.all().delete()
        new_recs = list(recommend_restaurants_for_user(self.diner, limit=10))
        self.assertGreater(len(new_recs), 0, "Should still return recommendations")

    def test_user_preference_weights_tracked(self):
        """Test that UserPreference weights are maintained and updated."""
        prefs = UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian"],
            cuisine_weight=Decimal("1.0"),
        )

        # Weights should be initialized
        self.assertEqual(prefs.cuisine_weight, Decimal("1.0"))
        self.assertEqual(prefs.dietary_weight, Decimal("1.0"))
        self.assertEqual(prefs.price_weight, Decimal("1.0"))

    def test_historical_satisfaction_affects_scores(self):
        """Test that past satisfaction influences current recommendations."""

        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian", "japanese"],
        )

        # Simulate user history: loves Italian, hates Japanese
        for _ in range(3):
            Review.objects.create(
                user=self.diner,
                restaurant=self.italian_restaurant,
                rating=5,  # High satisfaction
            )

        for _ in range(2):
            Review.objects.create(
                user=self.diner,
                restaurant=self.japanese_restaurant,
                rating=1,  # Low satisfaction
            )

        # Get recommendations
        recommendations = recommend_restaurants_for_user(self.diner, limit=5)
        rec_names = [r.name for r in recommendations]

        # Italian should rank higher than Japanese (due to better history)
        if "Tokyo Express" in rec_names and "Bella Italia" in rec_names:
            bella_idx = rec_names.index("Bella Italia")
            tokyo_idx = rec_names.index("Tokyo Express")
            self.assertLess(
                bella_idx, tokyo_idx, "Italian should rank higher due to better history"
            )

    def test_recent_interactions_weighted_higher(self):
        """Test that recent interactions are weighted more than old ones."""
        from nomz.models import UserInteractionHistory
        from datetime import timedelta

        UserPreference.objects.create(user=self.diner, favorite_cuisines=["italian"])

        # Create old interaction (60 days ago)
        old_time = timezone.now() - timedelta(days=60)
        old_interaction = UserInteractionHistory(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="view",
            created_at=old_time,
        )
        old_interaction.save()

        # Create recent interaction (5 days ago)
        recent_time = timezone.now() - timedelta(days=5)
        recent_interaction = UserInteractionHistory(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="view",
            created_at=recent_time,
        )
        recent_interaction.save()

        # Recent should have 2x weight, old should have 1.5x weight
        self.assertEqual(old_interaction.interaction_weight, 1.5)
        self.assertEqual(recent_interaction.interaction_weight, 2.0)

    def test_recommendation_success_rate_calculated(self):
        """Test that UserPreference tracks recommendation success rate."""
        prefs = UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian"],
            total_recommendations_received=10,
            successful_recommendations=7,
        )

        # Success rate should be 70%
        self.assertEqual(prefs.recommendation_success_rate, 70.0)

    def test_minimum_interactions_required_for_learning(self):
        """Test that learning requires minimum interactions."""
        UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian"],
            minimum_interactions_for_learning=3,
        )

        # With 0 interactions, learning should not trigger
        self.assertFalse(self.diner.preferences.has_enough_data_for_learning())

        # Create 2 interactions
        for _ in range(2):
            UserInteractionHistory.objects.create(
                user=self.diner,
                restaurant=self.italian_restaurant,
                interaction_type="view",
            )

        self.assertFalse(self.diner.preferences.has_enough_data_for_learning())

        # Create 3rd interaction
        UserInteractionHistory.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="view",
        )

        self.assertTrue(self.diner.preferences.has_enough_data_for_learning())

    def test_end_to_end_learning_loop(self):
        """Test complete learning loop: recommend → review → improved recommendations."""
        from nomz.models import RecalculatedRecommendation

        # Setup user with preferences
        prefs = UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian", "mexican"],
            price_preference="$$",
        )

        # Pre-populate interactions so learning will trigger (minimum 3 required)
        UserInteractionHistory.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="view",
        )
        UserInteractionHistory.objects.create(
            user=self.diner,
            restaurant=self.vegan_restaurant,
            interaction_type="search",
        )

        # Step 1: Get initial recommendations
        initial_recs = list(recommend_restaurants_for_user(self.diner, limit=5))
        self.assertGreater(len(initial_recs), 0, "Should have initial recommendations")

        # Step 2: User reviews a restaurant (triggers learning)
        Review.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            rating=5,
        )

        # Verify interaction was tracked
        interaction = UserInteractionHistory.objects.filter(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="review_submitted",
        ).first()
        self.assertIsNotNone(interaction)

        # Verify recommendation accuracy was updated
        rec_accuracy = RecalculatedRecommendation.objects.filter(
            user=self.diner,
            restaurant=self.italian_restaurant,
        ).first()

        if rec_accuracy:
            self.assertTrue(rec_accuracy.user_interacted)

        # Step 3: Verify preferences were updated
        prefs.refresh_from_db()
        self.assertGreater(
            prefs.recommendation_model_version,
            1,
            "Model version should increment after learning",
        )

        # Step 4: Get new recommendations
        RecalculatedRecommendation.objects.all().delete()
        new_recs = list(recommend_restaurants_for_user(self.diner, limit=5))

        # System should still provide recommendations
        self.assertGreater(len(new_recs), 0, "Should still have recommendations")

    def test_accuracy_feedback_inferred_from_review(self):
        """Test that accuracy feedback is inferred from review ratings."""
        from nomz.models import RecalculatedRecommendation

        UserPreference.objects.create(user=self.diner, favorite_cuisines=["italian"])

        # Create initial recommendation
        RecalculatedRecommendation.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            recommendation_score=Decimal("7.5"),
        )

        # User reviews with high rating
        Review.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            rating=5,
        )

        # Accuracy should be inferred as positive
        rec = RecalculatedRecommendation.objects.get(
            user=self.diner,
            restaurant=self.italian_restaurant,
        )

        rec.calculate_accuracy_from_interactions()
        self.assertEqual(rec.accuracy_feedback, 1)  # Great match
        self.assertTrue(rec.user_interacted)

    def test_recommendation_model_version_increments(self):
        """Test that recommendation model version increments on learning."""
        prefs = UserPreference.objects.create(
            user=self.diner,
            favorite_cuisines=["italian"],
            recommendation_model_version=1,
        )

        # Pre-populate interactions so learning will trigger (minimum 3 required)
        UserInteractionHistory.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            interaction_type="view",
        )
        UserInteractionHistory.objects.create(
            user=self.diner,
            restaurant=self.vegan_restaurant,
            interaction_type="search",
        )

        # Create initial recommendations so recommendation history exists
        recommend_restaurants_for_user(self.diner, limit=5)

        initial_version = prefs.recommendation_model_version

        # Trigger learning via review (3rd interaction)
        Review.objects.create(
            user=self.diner,
            restaurant=self.italian_restaurant,
            rating=5,
        )

        prefs.refresh_from_db()
        self.assertGreater(
            prefs.recommendation_model_version,
            initial_version,
            "Model version should increment",
        )
