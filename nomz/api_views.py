from __future__ import annotations

from decimal import Decimal

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Restaurant


def _safe_decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_score_text(value: Decimal | None) -> str:
    if value is None:
        return "No score"
    number = _safe_decimal_to_float(value)
    if number is None:
        return "No score"
    return f"{number:.0f}" if number.is_integer() else f"{number:.1f}"


def _coerce_float(raw_value: str) -> float | None:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


@require_GET
def map_restaurant_data(request):
    """
    Return restaurant marker-ready JSON for the map UI.
    """
    queryset = Restaurant.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(street__icontains=search)
            | Q(zip_code__icontains=search)
            | Q(borough__iexact=search)
            | Q(cuisine_tags__icontains=search)
        )

    borough = request.GET.get("borough", "").strip()
    if borough:
        queryset = queryset.filter(borough__iexact=borough)

    cuisine = request.GET.get("cuisine", "").strip()
    if cuisine:
        queryset = queryset.filter(cuisine_tags__icontains=cuisine)

    min_score_raw = request.GET.get("min_score", "").strip()
    if min_score_raw:
        min_score = _coerce_float(min_score_raw)
        if min_score is not None:
            queryset = queryset.filter(composite_score__gte=min_score)

    max_score_raw = request.GET.get("max_score", "").strip()
    if max_score_raw:
        max_score = _coerce_float(max_score_raw)
        if max_score is not None:
            queryset = queryset.filter(composite_score__lte=max_score)

    sw_lat = _coerce_float(request.GET.get("sw_lat", "").strip())
    ne_lat = _coerce_float(request.GET.get("ne_lat", "").strip())
    sw_lng = _coerce_float(request.GET.get("sw_lng", "").strip())
    ne_lng = _coerce_float(request.GET.get("ne_lng", "").strip())
    if all(v is not None for v in (sw_lat, ne_lat, sw_lng, ne_lng)):
        queryset = queryset.filter(
            latitude__gte=sw_lat,
            latitude__lte=ne_lat,
            longitude__gte=sw_lng,
            longitude__lte=ne_lng,
        )

    limit_raw = request.GET.get("limit", "").strip()
    try:
        limit = max(1, min(int(limit_raw), 4000))
    except (TypeError, ValueError):
        limit = 1000

    sort_by = request.GET.get("sort_by", "score_desc").strip()
    ordering = {
        "score_desc": ("-composite_score", "name"),
        "score_asc": ("composite_score", "name"),
        "name_asc": ("name",),
        "name_desc": ("-name",),
    }.get(sort_by, ("-composite_score", "name"))

    queryset = queryset.order_by(*ordering)[:limit]

    points = []
    for restaurant in queryset:
        lat = _safe_decimal_to_float(restaurant.latitude)
        lon = _safe_decimal_to_float(restaurant.longitude)
        if lat is None or lon is None:
            continue

        points.append(
            {
                "id": restaurant.id,
                "name": restaurant.display_name or restaurant.name,
                "address": ", ".join(
                    part
                    for part in [
                        restaurant.building or "",
                        restaurant.street or "",
                        restaurant.borough or "",
                        restaurant.zip_code or "",
                    ]
                    if part
                ),
                "borough": restaurant.borough,
                "zip_code": restaurant.zip_code,
                "phone": restaurant.phone,
                "cuisine_tags": restaurant.cuisine_tags or [],
                "latitude": lat,
                "longitude": lon,
                "composite_score": _safe_decimal_to_float(restaurant.composite_score),
                "composite_score_label": _safe_score_text(restaurant.composite_score),
                "grade": restaurant.grade_latest or "",
                "inspected_on": restaurant.last_inspection_date.isoformat()
                if restaurant.last_inspection_date
                else "",
            }
        )

    return JsonResponse({"count": len(points), "results": points})

