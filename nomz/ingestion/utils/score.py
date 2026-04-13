from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, Optional

from django.utils import timezone


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _to_local_date(value: object) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _normalize_5_to_100(value: Optional[float], fallback: float = 60.0) -> float:
    if value is None:
        return fallback
    return _clamp((float(value) / 5.0) * 100.0)


def _grade_score(grade: str) -> int:
    normalized = (grade or "").strip().upper()
    if not normalized:
        return 50

    if normalized.startswith("A"):
        return 95
    if normalized.startswith("B"):
        return 72
    if normalized.startswith("C"):
        return 42
    if "NOT" in normalized and "GRADED" in normalized:
        return 62

    return 50


def _violation_score(critical: int, noncritical: int) -> float:
    # Critical violations have much higher penalty than non-critical ones.
    base = 100.0 - (critical * 7.5) - (noncritical * 2.0)
    if critical >= 3:
        base -= 5.0
    return _clamp(base)


def _recency_score(last_inspection: Optional[date], reference_day: date) -> float:
    if not last_inspection:
        return 35.0

    delta = max((reference_day - last_inspection).days, 0)
    if delta <= 30:
        return 100.0
    if delta <= 90:
        return 88.0
    if delta <= 180:
        return 74.0
    if delta <= 365:
        return 58.0
    return 40.0


def _review_time_weight(age_days: int) -> float:
    if age_days <= 30:
        return 1.0
    if age_days <= 90:
        return 0.85
    if age_days <= 180:
        return 0.70
    if age_days <= 365:
        return 0.55
    return 0.40


def _average(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def _review_signal(reviews: Iterable[object], reference_day: date) -> Dict[str, object]:
    active_reviews = [review for review in reviews if review is not None]
    review_count = len(active_reviews)
    if review_count == 0:
        neutral_factor = {
            "overall_rating": None,
            "food_quality_rating": None,
            "service_quality_rating": None,
            "ambience_rating": None,
            "location_rating": None,
            "value_rating": None,
            "dietary_accommodation_rating": None,
            "cleanliness_rating": None,
        }
        return {
            "review_count": 0,
            "confidence": 0.0,
            "review_component_score": 60.0,
            "review_recency_score": 60.0,
            "factor_averages": neutral_factor,
            "factor_scores": {
                "overall_rating": 60.0,
                "food_quality_rating": 60.0,
                "service_quality_rating": 60.0,
                "ambience_rating": 60.0,
                "location_rating": 60.0,
                "value_rating": 60.0,
                "dietary_accommodation_rating": 60.0,
                "cleanliness_rating": 60.0,
            },
        }

    factor_averages = {
        "overall_rating": _average(float(item.rating) for item in active_reviews),
        "food_quality_rating": _average(
            float(item.food_quality_rating) for item in active_reviews
        ),
        "service_quality_rating": _average(
            float(item.service_quality_rating) for item in active_reviews
        ),
        "ambience_rating": _average(
            float(item.ambience_rating) for item in active_reviews
        ),
        "location_rating": _average(
            float(item.location_rating) for item in active_reviews
        ),
        "value_rating": _average(float(item.value_rating) for item in active_reviews),
        "dietary_accommodation_rating": _average(
            float(item.dietary_accommodation_rating) for item in active_reviews
        ),
        "cleanliness_rating": _average(
            float(item.cleanliness_rating) for item in active_reviews
        ),
    }

    # Experience quality score is review-dominant and weighted across dimensions.
    experience_5_point = (
        (factor_averages["food_quality_rating"] or 0) * 0.27
        + (factor_averages["service_quality_rating"] or 0) * 0.20
        + (factor_averages["ambience_rating"] or 0) * 0.14
        + (factor_averages["location_rating"] or 0) * 0.10
        + (factor_averages["value_rating"] or 0) * 0.12
        + (factor_averages["dietary_accommodation_rating"] or 0) * 0.07
        + (factor_averages["cleanliness_rating"] or 0) * 0.06
        + (factor_averages["overall_rating"] or 0) * 0.04
    )
    experience_score = _normalize_5_to_100(experience_5_point)

    recency_weighted_total = 0.0
    recency_total_weight = 0.0
    for item in active_reviews:
        created_at = _to_local_date(getattr(item, "created_at", None)) or reference_day
        age_days = max((reference_day - created_at).days, 0)
        weight = _review_time_weight(age_days)
        review_snapshot_5 = (
            (float(item.food_quality_rating) * 0.27)
            + (float(item.service_quality_rating) * 0.20)
            + (float(item.ambience_rating) * 0.14)
            + (float(item.location_rating) * 0.10)
            + (float(item.value_rating) * 0.12)
            + (float(item.dietary_accommodation_rating) * 0.07)
            + (float(item.cleanliness_rating) * 0.06)
            + (float(item.rating) * 0.04)
        )
        recency_weighted_total += review_snapshot_5 * weight
        recency_total_weight += weight

    recency_rating_5 = (
        recency_weighted_total / recency_total_weight if recency_total_weight else 3.0
    )
    recency_score = _normalize_5_to_100(recency_rating_5)

    # Bayesian smoothing keeps scores stable with low review counts.
    prior_score = 68.0
    prior_weight = 12.0
    smoothed_quality = (
        (experience_score * review_count) + (prior_score * prior_weight)
    ) / (review_count + prior_weight)
    review_component_score = (smoothed_quality * 0.88) + (recency_score * 0.12)
    review_component_score = _clamp(review_component_score)

    factor_scores = {
        key: _normalize_5_to_100(value) for key, value in factor_averages.items()
    }
    confidence = min(1.0, review_count / 25.0)

    return {
        "review_count": review_count,
        "confidence": round(confidence, 3),
        "review_component_score": round(review_component_score, 2),
        "review_recency_score": round(recency_score, 2),
        "factor_averages": factor_averages,
        "factor_scores": factor_scores,
    }


def _inspection_signal(
    latest_inspection: Optional[object], reference_day: date
) -> Dict[str, object]:
    if latest_inspection is None:
        return {
            "grade": "",
            "grade_score": 50,
            "violation_score": 55.0,
            "recency_score": 35.0,
            "inspection_component_score": 48.75,
            "last_inspection_date": None,
            "critical_violations": 0,
            "noncritical_violations": 0,
        }

    grade = (latest_inspection.grade or "").strip().upper()
    grade_points = _grade_score(grade)
    critical = int(latest_inspection.critical_violations or 0)
    noncritical = int(latest_inspection.noncritical_violations or 0)
    violation_points = _violation_score(critical, noncritical)
    recency_points = _recency_score(latest_inspection.inspection_date, reference_day)
    inspection_component = (
        (0.45 * grade_points) + (0.40 * violation_points) + (0.15 * recency_points)
    )

    return {
        "grade": grade,
        "grade_score": grade_points,
        "violation_score": round(violation_points, 2),
        "recency_score": round(recency_points, 2),
        "inspection_component_score": round(inspection_component, 2),
        "last_inspection_date": latest_inspection.inspection_date,
        "critical_violations": critical,
        "noncritical_violations": noncritical,
    }


def _price_value_signal(
    price_range: str, value_rating_average: Optional[float]
) -> float:
    if value_rating_average is None:
        return 58.0

    expected_value = {
        "$": 4.0,
        "$$": 3.8,
        "$$$": 3.5,
        "$$$$": 3.2,
    }.get((price_range or "$$").strip(), 3.8)
    gap = float(value_rating_average) - expected_value
    raw_score = 72.0 + (gap * 22.0)
    return round(_clamp(raw_score, 15.0, 100.0), 2)


def _operational_signal(restaurant: object) -> float:
    score = 88.0 if getattr(restaurant, "is_active", False) else 25.0
    if getattr(restaurant, "is_temporarily_unavailable", False):
        score -= 28.0
    if getattr(restaurant, "is_flagged", False):
        score -= 20.0
    if getattr(restaurant, "hours_open", None) and getattr(
        restaurant, "hours_close", None
    ):
        score += 5.0
    if getattr(restaurant, "latitude", None) and getattr(restaurant, "longitude", None):
        score += 4.0

    dining_out_profile = getattr(restaurant, "dining_out_profile", None)
    if dining_out_profile is not None:
        status = (getattr(dining_out_profile, "license_status", "") or "").lower()
        if "active" in status:
            score += 4.0
        elif any(token in status for token in ["suspend", "expired", "revoked"]):
            score -= 8.0

    return round(_clamp(score), 2)


def compute_composite_score_from_records(
    records, now=None
) -> Dict[str, float | int | str | None]:
    reference_day = _to_local_date(now) or timezone.localdate()
    latest = list(records)[0] if records else None
    inspection = _inspection_signal(latest, reference_day)
    return {
        "composite_score": inspection["inspection_component_score"],
        "grade": inspection["grade"],
        "grade_score": inspection["grade_score"],
        "violation_score": inspection["violation_score"],
        "recency_score": inspection["recency_score"],
        "last_inspection_date": inspection["last_inspection_date"],
        "critical_violations": inspection["critical_violations"],
        "noncritical_violations": inspection["noncritical_violations"],
        "inspection_component_score": inspection["inspection_component_score"],
    }


def compute_restaurant_composite_score(
    restaurant: object,
    *,
    as_of_date: Optional[date] = None,
) -> Dict[str, object]:
    reference_day = as_of_date or timezone.localdate()

    inspections = restaurant.inspections
    if as_of_date:
        latest_inspection = (
            inspections.filter(inspection_date__lte=as_of_date)
            .order_by("-inspection_date", "-id")
            .first()
        )
    else:
        latest_inspection = inspections.order_by("-inspection_date", "-id").first()

    reviews_qs = restaurant.reviews.filter(is_deleted=False, is_flagged=False)
    if as_of_date:
        reviews_qs = reviews_qs.filter(created_at__date__lte=as_of_date)
    reviews = list(reviews_qs)

    review_signal = _review_signal(reviews, reference_day)
    inspection_signal = _inspection_signal(latest_inspection, reference_day)
    price_value_score = _price_value_signal(
        getattr(restaurant, "price_range", "$$"),
        review_signal["factor_averages"].get("value_rating"),
    )
    operational_score = _operational_signal(restaurant)

    has_inspection = latest_inspection is not None

    if review_signal["review_count"] > 0:
        weights = {
            "review_experience": 0.65,
            "inspection_hygiene": 0.20,
            "price_value_alignment": 0.10,
            "operational_reliability": 0.05,
        }
    elif has_inspection:
        # No reviews yet: lean on inspections to spread scores until review volume grows.
        weights = {
            "review_experience": 0.05,
            "inspection_hygiene": 0.75,
            "price_value_alignment": 0.10,
            "operational_reliability": 0.10,
        }
    else:
        # Cold-start fallback when no user reviews exist yet.
        weights = {
            "review_experience": 0.20,
            "inspection_hygiene": 0.20,
            "price_value_alignment": 0.20,
            "operational_reliability": 0.40,
        }

    composite_score = (
        (review_signal["review_component_score"] * weights["review_experience"])
        + (
            inspection_signal["inspection_component_score"]
            * weights["inspection_hygiene"]
        )
        + (price_value_score * weights["price_value_alignment"])
        + (operational_score * weights["operational_reliability"])
    )

    breakdown = [
        {
            "label": "User Experience Signal",
            "raw_value": round(review_signal["review_component_score"], 2),
            "weight_percent": int(weights["review_experience"] * 100),
            "weighted_contribution": round(
                review_signal["review_component_score"] * weights["review_experience"],
                2,
            ),
            "description": (
                f"{review_signal['review_count']} review(s), confidence "
                f"{round(review_signal['confidence'] * 100, 1)}%"
            ),
        },
        {
            "label": "Inspection & Hygiene",
            "raw_value": round(inspection_signal["inspection_component_score"], 2),
            "weight_percent": int(weights["inspection_hygiene"] * 100),
            "weighted_contribution": round(
                inspection_signal["inspection_component_score"]
                * weights["inspection_hygiene"],
                2,
            ),
            "description": (
                f"Grade {inspection_signal['grade'] or 'N/A'} | "
                f"Critical {inspection_signal['critical_violations']} | "
                f"Non-critical {inspection_signal['noncritical_violations']}"
            ),
        },
        {
            "label": "Price-to-Value Fit",
            "raw_value": price_value_score,
            "weight_percent": int(weights["price_value_alignment"] * 100),
            "weighted_contribution": round(
                price_value_score * weights["price_value_alignment"], 2
            ),
            "description": "Derived from value ratings against expected value for price tier.",
        },
        {
            "label": "Operational Reliability",
            "raw_value": operational_score,
            "weight_percent": int(weights["operational_reliability"] * 100),
            "weighted_contribution": round(
                operational_score * weights["operational_reliability"], 2
            ),
            "description": "Based on profile status, temporary availability, and metadata quality.",
        },
    ]

    return {
        "composite_score": round(_clamp(composite_score), 2),
        "grade": inspection_signal["grade"],
        "grade_score": inspection_signal["grade_score"],
        "violation_score": inspection_signal["violation_score"],
        "recency_score": inspection_signal["recency_score"],
        "last_inspection_date": inspection_signal["last_inspection_date"],
        "critical_violations": inspection_signal["critical_violations"],
        "noncritical_violations": inspection_signal["noncritical_violations"],
        "inspection_component_score": inspection_signal["inspection_component_score"],
        "review_component_score": review_signal["review_component_score"],
        "review_count": review_signal["review_count"],
        "review_confidence": review_signal["confidence"],
        "review_recency_score": review_signal["review_recency_score"],
        "review_factor_scores": review_signal["factor_scores"],
        "review_factor_averages": review_signal["factor_averages"],
        "price_value_score": price_value_score,
        "operational_score": operational_score,
        "score_breakdown": breakdown,
        "weights": weights,
    }
