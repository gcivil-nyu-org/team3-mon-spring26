"""
Shared restaurant list ordering for map API and search views.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from django.db.models import Case, Count, F, IntegerField, QuerySet, When
from django.utils import timezone

# Backward-compatible aliases (map UI historically used score_* / name_*).
_SORT_ALIASES: dict[str, str] = {
    "score_desc": "composite_desc",
    "score_asc": "composite_asc",
}


def normalize_sort_key(sort_by: str) -> str:
    raw = (sort_by or "").strip()
    return _SORT_ALIASES.get(raw, raw) or "composite_desc"


def _price_rank_annotation():
    return Case(
        When(price_range="$", then=1),
        When(price_range="$$", then=2),
        When(price_range="$$$", then=3),
        When(price_range="$$$$", then=4),
        default=99,
        output_field=IntegerField(),
    )


def sort_restaurant_queryset(queryset: QuerySet, sort_by: str) -> QuerySet:
    """
    Apply ordering at the database. Uses grade_score_latest as inspection-based
    rating (higher is better). Popularity is proxied by inspection record count.
    """
    key = normalize_sort_key(sort_by)

    if key == "composite_desc":
        return queryset.order_by(F("composite_score").desc(nulls_last=True), "name")
    if key == "composite_asc":
        return queryset.order_by(F("composite_score").asc(nulls_last=True), "name")
    if key == "rating_desc":
        return queryset.order_by(F("grade_score_latest").desc(nulls_last=True), "name")
    if key == "rating_asc":
        return queryset.order_by(F("grade_score_latest").asc(nulls_last=True), "name")
    if key == "price_asc":
        return queryset.annotate(_sort_price_rank=_price_rank_annotation()).order_by(
            "_sort_price_rank", "name"
        )
    if key == "price_desc":
        return queryset.annotate(_sort_price_rank=_price_rank_annotation()).order_by(
            "-_sort_price_rank", "name"
        )
    if key == "popularity_desc":
        return queryset.annotate(_sort_popularity=Count("inspections")).order_by(
            "-_sort_popularity", "name"
        )
    if key == "popularity_asc":
        return queryset.annotate(_sort_popularity=Count("inspections")).order_by(
            "_sort_popularity", "name"
        )
    if key == "name_asc":
        return queryset.order_by("name")
    if key == "name_desc":
        return queryset.order_by("-name")

    return queryset.order_by(F("composite_score").desc(nulls_last=True), "name")


def recommend_restaurants_for_user(user, limit=10, use_learning=True):
    """
    Return a list of recommended restaurants based on user preferences with continuous refinement.

    ENHANCEMENTS:
    - Incorporates historical user interactions for learning
    - Uses time-weighted satisfaction scores
    - Dynamically adjusts recommendation weights based on past accuracy
    - Tracks recommendations for future accuracy measurement

    Args:
        user: User object to generate recommendations for
        limit: Maximum number of recommendations to return
        use_learning: Whether to use learned weights (default True)

    Returns:
        List of Restaurant objects ranked by recommendation score
    """
    from .models import (
        Restaurant,
        UserPreference,
    )

    try:
        prefs = user.preferences
    except UserPreference.DoesNotExist:
        return []

    # Check if user has any preferences defined
    nh = (prefs.neighborhood_preference or "").strip()
    if (
        not prefs.favorite_cuisines
        and not prefs.dietary_restrictions
        and not prefs.price_preference
        and not nh
    ):
        return []

    # Get base active restaurants
    base_qs = Restaurant.objects.filter(is_active=True, is_flagged=False)

    # ===== ENHANCED SCORING WITH LEARNING =====
    def calculate_enhanced_score(restaurant):
        """Enhanced scoring that incorporates historical learning"""
        score = 0
        matched = False

        component_scores = {
            "cuisine": 0,
            "price": 0,
            "dietary": 0,
            "neighborhood": 0,
            "quality": 0,
            "historical_satisfaction": 0,
        }

        # 1. CUISINE MATCHING (weighted by learned weight)
        if (
            prefs.favorite_cuisines
            and restaurant.cuisine_type in prefs.favorite_cuisines
        ):
            cuisine_score = 5 * float(prefs.cuisine_weight)
            score += cuisine_score
            component_scores["cuisine"] = cuisine_score
            matched = True

        # 2. PRICE MATCHING (weighted by learned weight)
        if prefs.price_preference and restaurant.price_range == prefs.price_preference:
            price_score = 3 * float(prefs.price_weight)
            score += price_score
            component_scores["price"] = price_score
            matched = True

        # 3. NEIGHBORHOOD MATCHING (weighted by learned weight)
        if prefs.neighborhood_preference and prefs.neighborhood_preference.strip():
            pref_nh = prefs.neighborhood_preference.strip().lower()
            if (
                restaurant.neighborhood and restaurant.neighborhood.lower() == pref_nh
            ) or (restaurant.borough and restaurant.borough.lower() == pref_nh):
                neighborhood_score = 2 * float(prefs.neighborhood_weight)
                score += neighborhood_score
                component_scores["neighborhood"] = neighborhood_score
                matched = True

        # 4. DIETARY RESTRICTIONS MATCHING (weighted by learned weight)
        dietary = [d.lower() for d in (prefs.dietary_restrictions or [])]
        if dietary:
            restaurant_tags = []
            if restaurant.cuisine_type:
                restaurant_tags.append(restaurant.cuisine_type.lower())
            if restaurant.cuisine_tags:
                restaurant_tags.extend(
                    [str(x).lower() for x in restaurant.cuisine_tags]
                )

            dietary_score = 0
            if "vegan" in dietary and "vegan" in restaurant_tags:
                dietary_score = 4
                matched = True
            elif "vegetarian" in dietary and "vegetarian" in restaurant_tags:
                dietary_score = 3
                matched = True
            elif "gluten-free" in dietary and "gluten-free" in restaurant_tags:
                dietary_score = 2
                matched = True
            elif "halal" in dietary and "halal" in restaurant_tags:
                dietary_score = 2
                matched = True
            elif "kosher" in dietary and "kosher" in restaurant_tags:
                dietary_score = 2
                matched = True

            score += dietary_score * float(prefs.dietary_weight)
            component_scores["dietary"] = dietary_score * float(prefs.dietary_weight)

        # If no preference matches, return 0
        if not matched:
            return 0, component_scores

        # 5. RESTAURANT QUALITY SCORE (composite score - weighted)
        if restaurant.composite_score is not None:
            try:
                quality_score = float(restaurant.composite_score) / 10.0
                score += quality_score * float(prefs.composite_score_weight)
                component_scores["quality"] = quality_score * float(
                    prefs.composite_score_weight
                )
            except (TypeError, ValueError):
                pass

        # ===== NEW: HISTORICAL SATISFACTION BOOST =====
        if use_learning and prefs.has_enough_data_for_learning():
            historical_satisfaction = calculate_historical_satisfaction_for_restaurant(
                user, restaurant
            )
            if historical_satisfaction > 0:
                satisfaction_boost = historical_satisfaction * float(
                    prefs.historical_satisfaction_weight
                )
                score += satisfaction_boost
                component_scores["historical_satisfaction"] = satisfaction_boost

        # ===== NEW: TIME-WEIGHTED INTERACTION BOOST =====
        if use_learning:
            time_weighted_boost = calculate_time_weighted_interaction_boost(
                user, restaurant
            )
            score += time_weighted_boost

        return score, component_scores

    # Calculate scores for all restaurants
    scored = [(calculate_enhanced_score(r), r) for r in base_qs]
    scored = sorted(
        scored, key=lambda x: (x[0][0], x[1].composite_score or 0), reverse=True
    )

    # Filter out zero-score entries
    filtered = [(score_tuple, r) for (score_tuple, r) in scored if score_tuple[0] > 0]
    result = [r for (score_tuple, r) in filtered[:limit]]

    # ===== NEW: RECORD RECOMMENDATIONS FOR ACCURACY TRACKING =====
    if use_learning:
        record_recommendations_for_accuracy_tracking(user, result, filtered[:limit])

    # ===== NEW: UPDATE RECOMMENDATION TRACKING =====
    if prefs and result:
        prefs.total_recommendations_received += len(result)
        prefs.last_recommendation_recalculated_at = timezone.now()
        prefs.save(
            update_fields=[
                "total_recommendations_received",
                "last_recommendation_recalculated_at",
            ]
        )

    return result


def calculate_historical_satisfaction_for_restaurant(user, restaurant):
    """
    Calculate satisfaction boost based on user's historical reviews of similar restaurants.

    If user rated similar restaurants highly, boost this restaurant's score.
    If user rated similar restaurants poorly, reduce this restaurant's score.

    Returns:
        Float: satisfaction bonus (-2 to +2)
    """
    from .models import Review

    # Get user's recent reviews (last 6 months)
    six_months_ago = timezone.now() - timedelta(days=180)
    recent_reviews = Review.objects.filter(
        user=user,
        restaurant__is_flagged=False,
        restaurant__is_active=True,
        created_at__gte=six_months_ago,
        is_deleted=False,
    ).select_related("restaurant")

    if not recent_reviews.exists():
        return 0

    # Calculate average rating for similar restaurants
    similar_reviews = []
    for review in recent_reviews:
        # Find reviews for restaurants with same cuisine type
        if review.restaurant.cuisine_type == restaurant.cuisine_type:
            similar_reviews.append(review)

    if not similar_reviews:
        return 0

    # Calculate average satisfaction
    avg_satisfaction = sum(r.rating for r in similar_reviews) / len(similar_reviews)

    # Normalize to -2 to +2 scale (5-point scale → -2 to +2)
    # Rating of 5 → +2 boost
    # Rating of 3 → 0 boost (neutral)
    # Rating of 1 → -2 boost
    normalized_satisfaction = (avg_satisfaction - 3) * 0.667

    return normalized_satisfaction


def calculate_time_weighted_interaction_boost(user, restaurant):
    """
    Calculate boost based on recent interactions with this specific restaurant.

    Recent positive interactions (reviews, saves) boost score.
    Time-weighted so recent interactions matter more.

    Returns:
        Float: interaction boost (0 to +1)
    """
    from .models import UserInteractionHistory

    # Get recent interactions with this restaurant (last 90 days)
    ninety_days_ago = timezone.now() - timedelta(days=90)
    interactions = UserInteractionHistory.objects.filter(
        user=user, restaurant=restaurant, created_at__gte=ninety_days_ago
    )

    if not interactions.exists():
        return 0

    # Calculate weighted boost from interactions
    boost = 0
    for interaction in interactions:
        interaction_boost = 0.1 * interaction.interaction_weight
        boost += interaction_boost

    # Cap boost at +1
    return min(boost, 1.0)


def record_recommendations_for_accuracy_tracking(
    user, recommendations, scored_restaurants
):
    """
    Record recommendations for later accuracy measurement.

    This allows us to track whether these recommendations led to user interactions
    and satisfaction, enabling continuous model improvement.
    """
    from .models import RecalculatedRecommendation

    for rank, (score_tuple, restaurant) in enumerate(
        scored_restaurants[: len(recommendations)], 1
    ):
        recommendation_score = Decimal(str(score_tuple[0]))
        component_scores = score_tuple[1]

        # Create record (or update if it already exists for today)
        RecalculatedRecommendation.objects.update_or_create(
            user=user,
            restaurant=restaurant,
            defaults={
                "recommendation_score": recommendation_score,
                "recommendation_rank": rank,
                "cuisine_score": Decimal(str(component_scores.get("cuisine", 0))),
                "price_score": Decimal(str(component_scores.get("price", 0))),
                "dietary_score": Decimal(str(component_scores.get("dietary", 0))),
                "neighborhood_score": Decimal(
                    str(component_scores.get("neighborhood", 0))
                ),
                "quality_score": Decimal(str(component_scores.get("quality", 0))),
                "historical_satisfaction_score": Decimal(
                    str(component_scores.get("historical_satisfaction", 0))
                ),
            },
        )
