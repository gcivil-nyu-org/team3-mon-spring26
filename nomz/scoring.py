from __future__ import annotations

from datetime import date
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from nomz.ingestion.utils.score import compute_restaurant_composite_score

SCORE_ALGORITHM_VERSION = "v2"


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _detect_score_anomalies(score_data, previous_score):
    anomalies = []
    composite_score = _safe_float(score_data.get("composite_score")) or 0.0
    review_count = int(score_data.get("review_count") or 0)
    review_confidence = _safe_float(score_data.get("review_confidence")) or 0.0
    last_inspection_date = score_data.get("last_inspection_date")

    if previous_score is not None:
        delta = composite_score - previous_score
        if abs(delta) >= 20:
            anomalies.append(
                {
                    "type": "large_delta",
                    "severity": "HIGH",
                    "message": "Composite score moved by 20+ points in one recalculation.",
                    "details": {
                        "previous_score": round(previous_score, 2),
                        "current_score": round(composite_score, 2),
                        "delta": round(delta, 2),
                    },
                }
            )

    if composite_score >= 85 and review_count < 3 and review_confidence < 0.20:
        anomalies.append(
            {
                "type": "low_confidence_high_score",
                "severity": "MEDIUM",
                "message": "High composite score with low review confidence.",
                "details": {
                    "composite_score": round(composite_score, 2),
                    "review_count": review_count,
                    "review_confidence": round(review_confidence, 3),
                },
            }
        )

    if isinstance(last_inspection_date, date):
        days_since_inspection = max(
            (timezone.localdate() - last_inspection_date).days,
            0,
        )
        if composite_score >= 80 and days_since_inspection > 365:
            anomalies.append(
                {
                    "type": "stale_inspection_high_score",
                    "severity": "MEDIUM",
                    "message": "High score with stale inspection data (>365 days).",
                    "details": {
                        "composite_score": round(composite_score, 2),
                        "days_since_inspection": days_since_inspection,
                        "last_inspection_date": last_inspection_date.isoformat(),
                    },
                }
            )

    return anomalies


def refresh_restaurant_composite(
    restaurant,
    *,
    trigger_source: str = "other",
    triggered_by=None,
    trigger_note: str = "",
):
    """
    Recompute and persist composite fields for a single restaurant.
    """
    from nomz.models import (
        CompositeScoreAnomaly,
        CompositeScoreHistory,
        SystemAuditLog,
    )

    previous_score = _safe_float(restaurant.composite_score)
    score_data = compute_restaurant_composite_score(restaurant)
    anomalies = _detect_score_anomalies(score_data, previous_score)
    restaurant.composite_score = score_data["composite_score"]
    restaurant.grade_latest = score_data["grade"]
    restaurant.grade_score_latest = score_data["grade_score"]
    restaurant.last_inspection_date = score_data["last_inspection_date"]
    restaurant.composite_score_calculated_at = timezone.now()

    with transaction.atomic():
        restaurant.save(
            update_fields=[
                "composite_score",
                "grade_latest",
                "grade_score_latest",
                "last_inspection_date",
                "composite_score_calculated_at",
                "updated_at",
            ]
        )

        history = CompositeScoreHistory.objects.create(
            restaurant=restaurant,
            algorithm_version=SCORE_ALGORITHM_VERSION,
            trigger_source=trigger_source,
            trigger_note=trigger_note[:255],
            triggered_by=(
                triggered_by
                if getattr(triggered_by, "is_authenticated", False)
                else None
            ),
            composite_score=score_data.get("composite_score"),
            previous_composite_score=previous_score,
            delta_from_previous=(
                round(
                    (_safe_float(score_data.get("composite_score")) or 0.0)
                    - previous_score,
                    2,
                )
                if previous_score is not None
                else None
            ),
            grade=score_data.get("grade") or "",
            grade_score=int(score_data.get("grade_score") or 0),
            last_inspection_date=score_data.get("last_inspection_date"),
            inspection_component_score=score_data.get("inspection_component_score")
            or 0,
            review_component_score=score_data.get("review_component_score") or 0,
            price_value_score=score_data.get("price_value_score") or 0,
            operational_score=score_data.get("operational_score") or 0,
            review_count=int(score_data.get("review_count") or 0),
            review_confidence=score_data.get("review_confidence") or 0,
            score_breakdown=score_data.get("score_breakdown") or [],
            score_inputs={
                "weights": score_data.get("weights") or {},
                "review_factor_scores": score_data.get("review_factor_scores") or {},
                "review_factor_averages": score_data.get("review_factor_averages")
                or {},
                "review_recency_score": score_data.get("review_recency_score"),
                "violation_score": score_data.get("violation_score"),
                "recency_score": score_data.get("recency_score"),
            },
            anomaly_flags=[item["type"] for item in anomalies],
            is_anomalous=bool(anomalies),
        )

        for anomaly in anomalies:
            CompositeScoreAnomaly.objects.create(
                restaurant=restaurant,
                score_history=history,
                anomaly_type=anomaly["type"],
                severity=anomaly["severity"],
                details={
                    "message": anomaly.get("message"),
                    **(anomaly.get("details") or {}),
                },
            )

        if anomalies:
            SystemAuditLog.objects.create(
                actor_user=(
                    triggered_by
                    if getattr(triggered_by, "is_authenticated", False)
                    else None
                ),
                actor_username=(
                    triggered_by.username
                    if getattr(triggered_by, "is_authenticated", False)
                    else ""
                ),
                level="WARNING",
                action="composite_score_anomaly_detected",
                metadata={
                    "restaurant_id": restaurant.id,
                    "history_id": history.id,
                    "trigger_source": trigger_source,
                    "anomalies": anomalies,
                },
            )

    score_data["anomalies"] = anomalies
    score_data["anomaly_count"] = len(anomalies)
    score_data["history_id"] = history.id
    return score_data


def refresh_restaurants_composite(restaurants: Iterable):
    """
    Recompute and persist scores for an iterable of Restaurant objects.
    """
    refreshed = 0
    for restaurant in restaurants:
        refresh_restaurant_composite(restaurant)
        refreshed += 1
    return refreshed
