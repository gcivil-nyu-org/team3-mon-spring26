from __future__ import annotations

from typing import Iterable

from django.db.models import Q, QuerySet

from .models import Restaurant

DIETARY_OPTIONS = [
    "vegan",
    "vegetarian",
    "non-vegetarian",
    "gluten-free",
    "halal",
    "kosher",
]


def coerce_float(raw_value: str | None) -> float | None:
    try:
        if raw_value is None or str(raw_value).strip() == "":
            return None
        return float(str(raw_value).strip())
    except (TypeError, ValueError):
        return None


def parse_bool(raw_value: str | None) -> bool:
    if raw_value is None:
        return False

    return str(raw_value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_multi_values(raw_values: str | Iterable[str] | None) -> list[str]:
    if raw_values is None:
        return []

    if isinstance(raw_values, str):
        values = [raw_values]
    else:
        values = list(raw_values)

    normalized: list[str] = []
    for value in values:
        if value is None:
            continue
        for piece in str(value).split(","):
            cleaned = piece.strip().lower()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)

    return normalized


def restaurant_ordering(sort_by: str = "score_desc") -> tuple[str, ...]:
    return {
        "score_desc": ("-composite_score", "name"),
        "score_asc": ("composite_score", "name"),
        "name_asc": ("name",),
        "name_desc": ("-name",),
        "grade_desc": ("-grade_score_latest", "-composite_score", "name"),
        "grade_asc": ("grade_score_latest", "name"),
    }.get(sort_by, ("-composite_score", "name"))


def apply_restaurant_filters(
    queryset: QuerySet[Restaurant],
    *,
    params,
    require_coordinates: bool = False,
) -> QuerySet[Restaurant]:
    queryset = queryset.filter(is_active=True)
    if require_coordinates:
        queryset = queryset.filter(latitude__isnull=False, longitude__isnull=False)

    search = (params.get("search") or params.get("q") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(street__icontains=search)
            | Q(zip_code__icontains=search)
            | Q(borough__iexact=search)
            | Q(cuisine__icontains=search)
            | Q(cuisine_type__icontains=search)
            | Q(cuisine_tags__icontains=search)
        )

    neighborhood = (params.get("neighborhood") or params.get("borough") or "").strip()
    if neighborhood:
        queryset = queryset.filter(
            Q(neighborhood__iexact=neighborhood) | Q(borough__iexact=neighborhood)
        )

    cuisine = (params.get("cuisine") or "").strip()
    if cuisine:
        queryset = queryset.filter(
            Q(cuisine__iexact=cuisine)
            | Q(cuisine_type__icontains=cuisine)
            | Q(cuisine_tags__icontains=cuisine)
        )

    price_range = (params.get("price_range") or "").strip()
    valid_price_ranges = {value for value, _ in Restaurant.PRICE_CHOICES}
    if price_range and price_range in valid_price_ranges:
        queryset = queryset.filter(price_range=price_range)

    min_composite = coerce_float(
        params.get("min_composite_score") or params.get("min_score")
    )
    if min_composite is not None and min_composite > 0:
        queryset = queryset.filter(composite_score__gte=min_composite)

    max_composite = coerce_float(
        params.get("max_composite_score") or params.get("max_score")
    )
    if max_composite is not None and max_composite < 100:
        queryset = queryset.filter(composite_score__lte=max_composite)

    if (
        min_composite is not None
        and max_composite is not None
        and min_composite > max_composite
    ):
        return queryset.none()

    min_rating = coerce_float(params.get("min_rating"))
    if min_rating is not None and min_rating > 0:
        queryset = queryset.filter(grade_score_latest__gte=int(min_rating))

    dietary_values = parse_multi_values(
        params.getlist("dietary")
        if hasattr(params, "getlist")
        else params.get("dietary")
    )
    for dietary in dietary_values:
        queryset = queryset.filter(
            Q(cuisine_tags__icontains=dietary) | Q(description__icontains=dietary)
        )

    return queryset


def apply_open_now_filter(restaurants: Iterable[Restaurant]) -> list[Restaurant]:
    return [restaurant for restaurant in restaurants if restaurant.is_open_now()]
