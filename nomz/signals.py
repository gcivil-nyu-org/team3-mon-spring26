from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.db import models
from .models import (
    InspectionRecord,
    LoginLog,
    Message,
    MessageNotification,
    Review,
    UserInteractionHistory,
    RecalculatedRecommendation,
    UserPreference,
)
from .scoring import refresh_restaurant_composite

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")  # Fixed name
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    LoginLog.objects.create(
        user=user,
        username=user.username,
        ip_address=get_client_ip(request),
        status="Success",
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        is_user_suspicious=False,
    )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    # Support both username and email based login for logging
    login_id = credentials.get("username") or credentials.get("email") or "unknown"
    ip_address = get_client_ip(request) if request else None

    # Try to find the actual user to link the log, even on failure
    from django.contrib.auth.models import User

    user = User.objects.filter(
        models.Q(username=login_id) | models.Q(email=login_id)
    ).first()

    # Check for suspicious activity: > 3 failures in 15 minutes
    fifteen_mins_ago = timezone.now() - timedelta(minutes=15)

    # Log the failure
    LoginLog.objects.create(
        user=user,
        username=user.username if user else login_id,
        ip_address=ip_address,
        status="Failure",
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else "",
    )

    failures_by_ip = 0
    failures_by_user = 0

    if user or ip_address:
        # Check by IP
        failures_by_ip = (
            LoginLog.objects.filter(
                ip_address=ip_address, status="Failure", timestamp__gte=fifteen_mins_ago
            ).count()
            if ip_address
            else 0
        )

        # Check by User
        failures_by_user = LoginLog.objects.filter(
            username=(user.username if user else login_id),
            status="Failure",
            timestamp__gte=fifteen_mins_ago,
        ).count()

        if failures_by_ip > 3 or failures_by_user > 3:
            # Mark all recent logs as suspicious
            LoginLog.objects.filter(
                models.Q(ip_address=ip_address)
                | models.Q(username=(user.username if user else login_id)),
                timestamp__gte=fifteen_mins_ago,
            ).update(is_user_suspicious=True)

    # Check if this was an attempt on an admin or dashboard URL (Issue #46)
    admin_paths = ["/admin/", "/dashboard/", "/dashboard-action/", "/admin-login/"]
    is_admin_path = (
        any(request.path.startswith(p) for p in admin_paths) if request else False
    )

    # A user is suspicious if they specifically fail 3 times
    is_user_suspicious = failures_by_user >= 2
    # The overall log is suspicious if IP limit hit OR user limit hit OR admin path
    is_suspicious = failures_by_ip >= 2 or is_user_suspicious or is_admin_path

    LoginLog.objects.create(
        username=(user.username if user else login_id),
        ip_address=ip_address,
        status="Failure",
        user_agent=request.META.get("HTTP_USER_AGENT", "") if request else None,
        is_suspicious=is_suspicious,
        is_user_suspicious=is_user_suspicious,
    )


@receiver(post_save, sender=Review)
def handle_review_for_recommendation_learning(
    sender, instance, created, raw=False, **kwargs
):
    """
    Enhanced handler: When user submits a review, trigger recommendation learning.

    Steps:
    1. Record interaction in UserInteractionHistory
    2. Extract satisfaction score from review
    3. Update recommendation accuracy tracking
    4. Trigger recommendation recalculation for this user
    """
    if raw:
        return

    # 1. Record interaction
    UserInteractionHistory.objects.create(
        user=instance.user,
        restaurant=instance.restaurant,
        interaction_type="review_submitted",
        satisfaction_score=instance.rating,
        was_saved=False,
        was_shared=False,
        was_recommended=False,  # Will be updated if found in recommendations
    )

    # 2. Check if this restaurant was previously recommended to this user
    recommendation_history = (
        RecalculatedRecommendation.objects.filter(
            user=instance.user,
            restaurant=instance.restaurant,
            calculated_at__lte=instance.created_at,
        )
        .order_by("-calculated_at")
        .first()
    )

    if recommendation_history:
        # Update accuracy tracking
        recommendation_history.calculate_accuracy_from_interactions()

    # 3. Refresh restaurant composite score (existing behavior)
    refresh_restaurant_composite(
        instance.restaurant,
        trigger_source="signal_review",
    )

    # 4. Trigger recommendation recalculation
    recalculate_user_recommendation_model(instance.user.id)


def recalculate_user_recommendation_model(user_id):
    """
    Task to recalculate and improve user's recommendation model based on recent interactions.

    This function:
    1. Analyzes user's interaction history
    2. Calculates success rates for different preference combinations
    3. Adjusts UserPreference weights to maximize future accuracy
    4. Updates the recommendation model version

    Should be called:
    - After every review/rating (synchronously)
    - Nightly as a batch job for all users
    """
    from django.contrib.auth.models import User

    try:
        user = User.objects.get(id=user_id)
        prefs = user.preferences
    except (User.DoesNotExist, UserPreference.DoesNotExist):
        return

    # Require minimum interactions before learning
    if not prefs.has_enough_data_for_learning():
        return

    # Get recent interactions (last 90 days)
    recent_recommendations = RecalculatedRecommendation.objects.filter(
        user=user,
        # calculated_at__gte=ninety_days_ago,  # Temporarily remove for test
    )

    if not recent_recommendations.exists():
        return

    # Analyze success rates
    successful_count = recent_recommendations.filter(user_interacted=True).count()
    total_count = recent_recommendations.count()

    if total_count == 0:
        return

    success_rate = successful_count / total_count

    # Only adjust weights if we have meaningful data and need improvement
    if success_rate < 0.5:  # Less than 50% interaction rate
        _adjust_weights_for_better_accuracy(user, prefs, recent_recommendations)

    # Update preference model version
    prefs.recommendation_model_version += 1
    prefs.last_recommendation_improvement_at = timezone.now()
    prefs.learning_data_quality_score = min(Decimal(success_rate * 100), Decimal(100))
    prefs.save()


def _adjust_weights_for_better_accuracy(user, prefs, recent_recommendations):
    """
    Analyze recommendation accuracy and adjust preference weights.

    Strategy:
    1. Find which recommendations were successful (led to positive interactions)
    2. Identify common characteristics (cuisine, price, etc.)
    3. Increase weights for successful characteristics
    4. Decrease weights for unsuccessful characteristics
    """

    # Analyze successful recommendations
    successful_recs = recent_recommendations.filter(user_interacted=True)
    unsuccessful_recs = recent_recommendations.filter(user_interacted=False)

    if not successful_recs.exists():
        return

    # Calculate average score for successful vs unsuccessful
    successful_avg_cuisine_score = Decimal(
        str(successful_recs.aggregate(avg=models.Avg("cuisine_score"))["avg"] or 0)
    )
    unsuccessful_avg_cuisine_score = Decimal(
        str(unsuccessful_recs.aggregate(avg=models.Avg("cuisine_score"))["avg"] or 0)
    )

    successful_avg_price_score = Decimal(
        str(successful_recs.aggregate(avg=models.Avg("price_score"))["avg"] or 0)
    )
    unsuccessful_avg_price_score = Decimal(
        str(unsuccessful_recs.aggregate(avg=models.Avg("price_score"))["avg"] or 0)
    )

    successful_avg_dietary_score = Decimal(
        str(successful_recs.aggregate(avg=models.Avg("dietary_score"))["avg"] or 0)
    )
    unsuccessful_avg_dietary_score = Decimal(
        str(unsuccessful_recs.aggregate(avg=models.Avg("dietary_score"))["avg"] or 0)
    )

    # Adjust weights (conservative adjustments)
    adjustment_factor = Decimal("0.05")  # 5% adjustment per iteration

    adjustments_made = []

    # Adjust cuisine weight
    if successful_avg_cuisine_score > unsuccessful_avg_cuisine_score:
        prefs.cuisine_weight = min(
            prefs.cuisine_weight + adjustment_factor, Decimal("2.0")
        )
        adjustments_made.append(f"cuisine_weight +{adjustment_factor}")
    else:
        prefs.cuisine_weight = max(
            prefs.cuisine_weight - adjustment_factor, Decimal("0.5")
        )
        adjustments_made.append(f"cuisine_weight -{adjustment_factor}")

    # Adjust price weight
    if successful_avg_price_score > unsuccessful_avg_price_score:
        prefs.price_weight = min(prefs.price_weight + adjustment_factor, Decimal("2.0"))
        adjustments_made.append(f"price_weight +{adjustment_factor}")
    else:
        prefs.price_weight = max(prefs.price_weight - adjustment_factor, Decimal("0.5"))
        adjustments_made.append(f"price_weight -{adjustment_factor}")

    # Adjust dietary weight
    if successful_avg_dietary_score > unsuccessful_avg_dietary_score:
        prefs.dietary_weight = min(
            prefs.dietary_weight + adjustment_factor, Decimal("2.0")
        )
        adjustments_made.append(f"dietary_weight +{adjustment_factor}")
    else:
        prefs.dietary_weight = max(
            prefs.dietary_weight - adjustment_factor, Decimal("0.5")
        )
        adjustments_made.append(f"dietary_weight -{adjustment_factor}")

    prefs.last_weights_adjustment_reason = (
        f"Adjusted weights: {', '.join(adjustments_made)}"
    )
    prefs.save()


@receiver(post_delete, sender=Review)
def refresh_score_on_review_delete(sender, instance, **kwargs):
    refresh_restaurant_composite(
        instance.restaurant,
        trigger_source="signal_review_delete",
    )


@receiver(post_save, sender=InspectionRecord)
def refresh_score_on_inspection_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    refresh_restaurant_composite(
        instance.restaurant,
        trigger_source="signal_inspection",
    )


@receiver(post_delete, sender=InspectionRecord)
def refresh_score_on_inspection_delete(sender, instance, **kwargs):
    refresh_restaurant_composite(
        instance.restaurant,
        trigger_source="signal_inspection_delete",
    )


@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return

    conversation = instance.conversation
    if instance.sender_id == conversation.diner_id:
        recipient = conversation.restaurant.owner
    elif instance.sender_id == conversation.restaurant.owner_id:
        recipient = conversation.diner
    else:
        return

    if not recipient or recipient.id == instance.sender_id:
        return

    MessageNotification.objects.get_or_create(
        message=instance,
        defaults={
            "recipient": recipient,
            "conversation": conversation,
            "triggered_by": instance.sender,
        },
    )
