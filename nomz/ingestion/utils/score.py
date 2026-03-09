from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from django.utils import timezone


def _grade_score(grade: str) -> int:
    normalized = (grade or "").strip().upper()
    if not normalized:
        return 50

    if normalized.startswith("A"):
        return 95
    if normalized.startswith("B"):
        return 70
    if normalized.startswith("C"):
        return 40
    if "NOT" in normalized and "GRADED" in normalized:
        return 60
    if normalized in {"N", "Z", "P", "B+", "A+", "A-"}:
        if normalized.startswith("A"):
            return 95
        if normalized.startswith("B"):
            return 70
        if normalized.startswith("C"):
            return 40

    return 50


def _violation_score(critical: int, noncritical: int) -> float:
    base = 100.0
    base -= critical * 2
    base -= noncritical * 0.5
    if critical + noncritical > 5:
        base -= 5
    return max(0.0, base)


def _recency_score(last_inspection: Optional[date]) -> float:
    if not last_inspection:
        return 0.0

    delta = (timezone.localdate() - last_inspection).days
    if delta < 30:
        return 100.0
    if delta < 90:
        return 85.0
    if delta < 180:
        return 70.0
    if delta < 365:
        return 55.0
    return 30.0


def compute_composite_score_from_records(records, now=None) -> Dict[str, float | int | str | None]:
    latest = list(records)[0] if records else None
    if not latest:
        return {
            "composite_score": 50.0,
            "grade": "",
            "grade_score": 50,
            "violation_score": 0.0,
            "recency_score": 0.0,
            "last_inspection_date": None,
            "critical_violations": 0,
            "noncritical_violations": 0,
        }

    grade = (latest.grade or "").strip().upper()
    grade_points = _grade_score(grade)

    critical = int(latest.critical_violations or 0)
    noncritical = int(latest.noncritical_violations or 0)
    violation_points = _violation_score(critical, noncritical)
    recency_points = _recency_score(latest.inspection_date)

    composite = (0.50 * grade_points) + (0.35 * violation_points) + (0.15 * recency_points)

    return {
        "composite_score": round(composite, 2),
        "grade": grade,
        "grade_score": grade_points,
        "violation_score": violation_points,
        "recency_score": recency_points,
        "last_inspection_date": latest.inspection_date,
        "critical_violations": critical,
        "noncritical_violations": noncritical,
    }
