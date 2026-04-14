from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from nomz.models import (
    CompositeScoreAnomaly,
    CompositeScoreHistory,
    DataIngestionRun,
    DiningOutLocation,
    FriendConversation,
    FriendMessage,
    FriendSharedRestaurant,
    InspectionRecord,
    LoginLog,
    Message,
    MessageNotification,
    ModerationReport,
    RecalculatedRecommendation,
    RecommendationModelMetric,
    Restaurant,
    RestaurantOwnershipClaim,
    RestaurantSourceRecord,
    RestaurantSearch,
    Review,
    ReviewResponse,
    SystemAlert,
    SystemAuditLog,
    SystemPerformanceMetric,
    SystemPerformanceSnapshot,
    UserInteractionHistory,
    UserPreference,
    UserProfile,
)


class RestaurantOwnershipClaimCleanPendingTests(TestCase):
    def setUp(self):
        self.claimant_1 = User.objects.create_user(
            username="claimant1", email="claimant1@test.com", password="testpass123"
        )
        self.claimant_2 = User.objects.create_user(
            username="claimant2", email="claimant2@test.com", password="testpass123"
        )
        self.restaurant_1 = Restaurant.objects.create(name="Claim Target 1")
        self.restaurant_2 = Restaurant.objects.create(name="Claim Target 2")

    def test_clean_allows_pending_claim_when_no_conflicts(self):
        claim = RestaurantOwnershipClaim(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )
        claim.full_clean()

    def test_clean_rejects_when_claimant_already_has_pending_claim(self):
        RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )

        conflicting_claim = RestaurantOwnershipClaim(
            claimant=self.claimant_1,
            restaurant=self.restaurant_2,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )

        with self.assertRaisesMessage(
            ValidationError, "You already have a pending ownership claim."
        ):
            conflicting_claim.full_clean()

    def test_clean_rejects_when_restaurant_already_has_pending_claim(self):
        RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )

        conflicting_claim = RestaurantOwnershipClaim(
            claimant=self.claimant_2,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )

        with self.assertRaisesMessage(
            ValidationError, "There is already a pending claim for this restaurant."
        ):
            conflicting_claim.full_clean()

    def test_clean_skips_pending_checks_for_non_pending_status(self):
        RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )

        approved_claim = RestaurantOwnershipClaim(
            claimant=self.claimant_1,
            restaurant=self.restaurant_2,
            status=RestaurantOwnershipClaim.STATUS_APPROVED,
        )
        approved_claim.full_clean()

    def test_approve_rejects_non_pending_claim(self):
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_REJECTED,
        )
        with self.assertRaisesMessage(
            ValidationError, "Only pending claims can be approved."
        ):
            claim.approve()

    def test_approve_rejects_when_claimant_already_owns_other_restaurant(self):
        Restaurant.objects.create(name="Owned Spot", owner=self.claimant_1)
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )
        with self.assertRaisesMessage(
            ValidationError, "Claimant already owns another restaurant profile."
        ):
            claim.approve()

    def test_approve_rejects_when_restaurant_owned_by_different_user(self):
        self.restaurant_1.owner = self.claimant_2
        self.restaurant_1.save(update_fields=["owner"])
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )
        with self.assertRaisesMessage(
            ValidationError, "Restaurant is already assigned to another owner."
        ):
            claim.approve()

    def test_reject_rejects_non_pending_claim(self):
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=self.claimant_1,
            restaurant=self.restaurant_1,
            status=RestaurantOwnershipClaim.STATUS_APPROVED,
        )
        with self.assertRaisesMessage(
            ValidationError, "Only pending claims can be rejected."
        ):
            claim.reject()


class ModelsStringAndBranchCoverageTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", password="pass12345")
        self.user2 = User.objects.create_user(username="u2", password="pass12345")
        self.restaurant = Restaurant.objects.create(name="Model Spot", owner=self.user1)

    def test_basic_str_methods(self):
        self.assertEqual(str(UserProfile(user=self.user1, role="diner")), "u1 - diner")
        self.assertEqual(str(RestaurantSearch(name="Search Name")), "Search Name")
        self.assertIn("Model Spot", str(self.restaurant))
        self.assertTrue(self.restaurant.can_be_managed_by(self.user1))
        self.assertFalse(self.restaurant.can_be_managed_by(self.user2))

        log_no_user = LoginLog.objects.create(username="fallback", status="Success")
        log_with_user = LoginLog.objects.create(
            username="ignored", status="Failure", user=self.user1
        )
        self.assertEqual(str(log_no_user), "fallback - Success")
        self.assertEqual(str(log_with_user), "u1 - Failure")

        self.assertIn(
            "runset | running",
            str(DataIngestionRun.objects.create(dataset="runset", status="running")),
        )
        self.assertIn(
            "DiningOutProfile",
            str(DiningOutLocation.objects.create(restaurant=self.restaurant)),
        )
        self.assertIn(
            "pending",
            str(
                RestaurantOwnershipClaim.objects.create(
                    claimant=self.user1, restaurant=self.restaurant
                )
            ),
        )
        self.assertEqual(
            str(
                RestaurantSourceRecord.objects.create(
                    restaurant=self.restaurant,
                    source=RestaurantSourceRecord.SOURCE_EATERIES,
                    external_id="ext-1",
                    external_name="External Name",
                )
            ),
            "EATERIES ext-1",
        )

    def test_more_str_methods_and_actor_fallbacks(self):
        history = CompositeScoreHistory.objects.create(
            restaurant=self.restaurant,
            trigger_source=CompositeScoreHistory.TRIGGER_OTHER,
            composite_score=88,
        )
        anomaly = CompositeScoreAnomaly.objects.create(
            restaurant=self.restaurant,
            score_history=history,
            anomaly_type=CompositeScoreAnomaly.TYPE_LARGE_DELTA,
            is_resolved=False,
        )
        self.assertIn("open", str(anomaly))
        self.assertIn("score=", str(history))

        interaction = UserInteractionHistory.objects.create(
            user=self.user1, restaurant=self.restaurant, interaction_type="view"
        )
        self.assertIn("Restaurant View", str(interaction))
        interaction.created_at = timezone.now() - timedelta(days=120)
        interaction.save(update_fields=["created_at"])
        self.assertEqual(interaction.interaction_weight, 1.0)

        pref = UserPreference.objects.create(user=self.user1)
        self.assertIn("Preferences for u1", str(pref))

        rec = RecalculatedRecommendation.objects.create(
            user=self.user1,
            restaurant=self.restaurant,
            recommendation_score=77,
            accuracy_feedback=0,
        )
        self.assertIn("Rec: u1", str(rec))
        self.assertTrue(rec.is_accurate)

        metric = RecommendationModelMetric.objects.create(
            avg_recommendation_accuracy=60,
            total_recommendations_given=1,
            total_users_with_recommendations=1,
        )
        self.assertIn("Recommendation Metrics", str(metric))
        metric.avg_recommendation_accuracy = None
        self.assertIsNone(metric.month_over_month_improvement)

        prev = RecommendationModelMetric.objects.create(
            avg_recommendation_accuracy=50,
            total_recommendations_given=1,
            total_users_with_recommendations=1,
        )
        prev.metric_date = metric.metric_date - timedelta(days=31)
        prev.save(update_fields=["metric_date"])
        metric.avg_recommendation_accuracy = None
        self.assertIsNone(metric.month_over_month_improvement)

        audit_with_username = SystemAuditLog(
            actor_username="manual_actor", level="INFO", action="test_action"
        )
        audit_with_user = SystemAuditLog(
            actor_user=self.user1, level="INFO", action="test_action"
        )
        self.assertIn("(manual_actor)", str(audit_with_username))
        self.assertIn("(u1)", str(audit_with_user))

    def test_metrics_alert_review_response_and_conversation_branches(self):
        perf = SystemPerformanceMetric.objects.create(
            method="GET", path="/x", duration_ms=10, status_code=200
        )
        snap = SystemPerformanceSnapshot.objects.create(
            interval_start=perf.created_at,
            interval_end=perf.created_at,
            total_requests=1,
            error_requests=0,
            error_rate=0,
            avg_latency_ms=10,
            max_latency_ms=10,
        )
        alert = SystemAlert.objects.create(
            alert_type="HIGH_ERROR_RATE", severity="HIGH", message="m", is_active=False
        )
        self.assertIn("GET /x 200", str(perf))
        self.assertIn(" - ", str(snap))
        self.assertIn("resolved", str(alert))

        review = Review.objects.create(
            restaurant=self.restaurant,
            user=self.user1,
            rating=4,
            food_quality_rating=4,
            service_quality_rating=4,
            ambience_rating=4,
            location_rating=4,
            value_rating=4,
            dietary_accommodation_rating=4,
            cleanliness_rating=4,
        )
        self.assertIn("Review by u1", str(review))
        self.assertEqual(review.experience_rating, 4.0)

        bad_response = ReviewResponse(
            review=review,
            restaurant=self.restaurant,
            responder=self.user2,
            response_text="x",
        )
        with self.assertRaisesMessage(
            ValidationError, "Only the restaurant owner can submit a public response."
        ):
            bad_response.clean()

        mismatch_response = ReviewResponse(
            review=review,
            restaurant=Restaurant.objects.create(name="Other Spot", owner=self.user2),
            responder=self.user1,
            response_text="x",
        )
        with self.assertRaisesMessage(
            ValidationError,
            "Review response restaurant does not match the review's restaurant.",
        ):
            mismatch_response.clean()

        good_response = ReviewResponse.objects.create(
            review=review,
            restaurant=self.restaurant,
            responder=self.user1,
            response_text="Thanks!",
        )
        self.assertIn("Response by u1", str(good_response))

        conversation = FriendConversation.objects.create(is_group=True, name="Group1")
        self.assertEqual(str(conversation), "Group: Group1")
        message = FriendMessage.objects.create(
            conversation=conversation, sender=self.user1
        )
        self.assertIn("FriendMessage by u1", str(message))
        shared = FriendSharedRestaurant.objects.create(
            conversation=conversation, restaurant=self.restaurant, added_by=self.user1
        )
        self.assertIn("Model Spot in", str(shared))

    def test_message_and_moderation_str_paths(self):
        from nomz.models import Conversation

        convo = Conversation.objects.create(
            restaurant=self.restaurant, diner=self.user2
        )
        msg = Message.objects.create(
            conversation=convo, sender=self.user1, body="hello"
        )
        note = MessageNotification.objects.get(message=msg)
        self.assertIn("Message", str(msg))
        self.assertIn("Notification for u2", str(note))
        self.assertEqual(str(convo), "Model Spot <-> u2")

        report_user = ModerationReport.objects.create(
            reporter=self.user1,
            reported_user=self.user2,
            reason="OTHER",
            details="x",
        )
        report_review = ModerationReport.objects.create(
            reporter=self.user1,
            review=Review.objects.create(
                restaurant=self.restaurant, user=self.user2, rating=3
            ),
            reason="OTHER",
            details="y",
        )
        self.assertIn("User", str(report_user))
        self.assertIn("Review", str(report_review))

    def test_remaining_model_branches(self):
        restaurant_without_hours = Restaurant(
            name="NoHours", hours_open=None, hours_close=None
        )
        self.assertFalse(restaurant_without_hours.is_open_now())

        with patch(
            "nomz.models.timezone.now",
            return_value=timezone.now().replace(
                hour=12, minute=0, second=0, microsecond=0
            ),
        ):
            always_open = Restaurant(
                name="AlwaysOpen",
                is_active=True,
                is_temporarily_unavailable=False,
                hours_open=datetime.strptime("09:00", "%H:%M").time(),
                hours_close=datetime.strptime("21:00", "%H:%M").time(),
            )
            self.assertTrue(always_open.is_open_now())

        rec = RecalculatedRecommendation.objects.create(
            user=self.user1,
            restaurant=self.restaurant,
            recommendation_score=50,
        )
        Review.objects.create(
            restaurant=self.restaurant,
            user=self.user1,
            rating=2,
        )
        rec.calculate_accuracy_from_interactions()
        rec.refresh_from_db()
        self.assertEqual(rec.accuracy_feedback, -1)

        rec_neutral = RecalculatedRecommendation.objects.create(
            user=self.user1,
            restaurant=self.restaurant,
            recommendation_score=51,
        )
        Review.objects.create(
            restaurant=self.restaurant,
            user=self.user1,
            rating=3,
        )
        rec_neutral.calculate_accuracy_from_interactions()
        rec_neutral.refresh_from_db()
        self.assertEqual(rec_neutral.accuracy_feedback, 0)

        insp = InspectionRecord.objects.create(
            restaurant=self.restaurant,
            inspection_date=timezone.now().date(),
            inspection_key="i1",
        )
        self.assertEqual(str(insp), f"{self.restaurant.id}:i1")

        direct_chat = FriendConversation.objects.create()
        direct_chat.participants.add(self.user1, self.user2)
        self.assertEqual(str(direct_chat), "Chat: u1, u2")
