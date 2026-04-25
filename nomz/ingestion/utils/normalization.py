from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, List

NYC_MIN_LAT = Decimal("40.0")
NYC_MAX_LAT = Decimal("41.5")
NYC_MIN_LON = Decimal("-75.5")
NYC_MAX_LON = Decimal("-72.0")


def to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def normalize_text(value: Any) -> str:
    text = to_str(value)
    if not text:
        return ""
    return " ".join(text.replace("\u00a0", " ").split()).upper()


def first_non_empty(row: dict, keys: Iterable[str]) -> str:
    for key in keys:
        value = to_str(row.get(key))
        if value:
            return value
    return ""


def to_decimal_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    cleaned = to_str(value).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        normalized = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return str(normalized.quantize(Decimal("0.000001")))


def sanitize_nyc_coordinate_pair(
    latitude: Any,
    longitude: Any,
) -> tuple[str | None, str | None]:
    lat_text = to_decimal_str(latitude)
    lon_text = to_decimal_str(longitude)
    if lat_text is None or lon_text is None:
        return lat_text, lon_text

    try:
        lat = Decimal(lat_text)
        lon = Decimal(lon_text)
    except (InvalidOperation, ValueError):
        return None, None

    # Socrata sometimes emits placeholder 0/0 for missing coordinates.
    if lat == 0 and lon == 0:
        return None, None

    if not (NYC_MIN_LAT <= lat <= NYC_MAX_LAT and NYC_MIN_LON <= lon <= NYC_MAX_LON):
        return None, None

    return lat_text, lon_text


def split_list_fields(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [normalize_text(item) for item in raw if normalize_text(item)]
    text = to_str(raw)
    if not text:
        return []
    parts = [item.strip() for item in text.replace("|", ",").split(",")]
    return [part.upper() for part in parts if part.strip()]


@dataclass(frozen=True)
class Coordinate:
    latitude: str | None
    longitude: str | None
