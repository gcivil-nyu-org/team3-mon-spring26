from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, List


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
