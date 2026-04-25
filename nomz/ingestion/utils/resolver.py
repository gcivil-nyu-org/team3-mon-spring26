from __future__ import annotations

from dataclasses import dataclass
import re
from difflib import SequenceMatcher
from math import atan2, cos, radians, sin, sqrt
from typing import Dict, Iterable, Optional, Tuple

_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")


@dataclass(frozen=True)
class MatchResult:
    restaurant_payload: Optional[Dict]
    score: float
    strategy: str


def _to_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_or_close_zip(zip_a: str, zip_b: str) -> bool:
    return (zip_a or "").strip()[:5] == (zip_b or "").strip()[:5] and bool(
        zip_a and zip_b
    )


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.upper(), b.upper()).ratio()


def _distance_miles(
    lat_a: object, lon_a: object, lat_b: object, lon_b: object
) -> Optional[float]:
    lat1 = _to_float(lat_a)
    lon1 = _to_float(lon_a)
    lat2 = _to_float(lat_b)
    lon2 = _to_float(lon_b)
    if None in (lat1, lon1, lat2, lon2):
        return None

    # Haversine distance
    r = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    h = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    d = 2 * r * atan2(sqrt(h), sqrt(1 - h))
    return d


@dataclass(frozen=True)
class MatchCandidate:
    record_id: str
    name: str
    address_key: str
    street: str
    zip_code: str
    borough: str
    latitude: Optional[float]
    longitude: Optional[float]


def build_address_key(building: str, street: str, zip_code: str) -> str:
    b = _normalize_for_match(building)
    s = _normalize_for_match(street)
    z = (zip_code or "").strip()[:5]
    return f"{b}|{s}|{z}"


def _normalize_for_match(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    text = text.replace(" STREET", " ST")
    text = text.replace(" AVENUE", " AVE")
    text = text.replace(" BOULEVARD", " BLVD")
    text = text.replace(" ROAD", " RD")
    text = text.replace(" AV", " AV")
    text = _NON_ALNUM_RE.sub("", text)
    return text


def score_match(
    incoming: Dict,
    candidate: Dict,
) -> float:
    incoming_name = (incoming.get("name_normalized") or "").upper()
    candidate_name = (candidate.get("name_normalized") or "").upper()
    incoming_street = (incoming.get("street") or "").upper()
    candidate_street = (candidate.get("street") or "").upper()
    incoming_zip = (incoming.get("zip_code") or "").strip()[:5]
    candidate_zip = (candidate.get("zip_code") or "").strip()[:5]

    exact_key_in = build_address_key(
        incoming.get("building", ""),
        incoming_street,
        incoming_zip,
    )
    exact_key_cand = build_address_key(
        candidate.get("building", ""),
        candidate_street,
        candidate_zip,
    )
    if (
        incoming_name
        == (candidate.get("name") or candidate.get("name_normalized", "")).upper()
        and exact_key_in == exact_key_cand
    ):
        return 1.0

    name_score = _similarity(incoming_name, candidate_name)
    address_score = _similarity(incoming_street, candidate_street)
    zip_match = 1.0 if _same_or_close_zip(incoming_zip, candidate_zip) else 0.0

    distance = _distance_miles(
        incoming.get("latitude"),
        incoming.get("longitude"),
        candidate.get("latitude"),
        candidate.get("longitude"),
    )
    distance_score = 0.0
    if distance is not None:
        if distance <= 0.05:
            distance_score = 1.0
        elif distance <= 0.2:
            distance_score = 0.8
        elif distance <= 0.5:
            distance_score = 0.6

    score = (
        (0.65 * name_score)
        + (0.2 * address_score)
        + (0.1 * zip_match)
        + (0.05 * distance_score)
    )
    return max(0.0, min(1.0, score))


def resolve_restaurant(
    incoming: Dict,
    candidates: Iterable[Dict],
    threshold: float = 0.86,
) -> Tuple[Optional[Dict], float, str]:
    incoming_name = (incoming.get("name_normalized") or "").upper()
    incoming_street = _normalize_for_match(incoming.get("street", ""))
    incoming_zip = (incoming.get("zip_code") or "").strip()[:5]
    incoming_borough = (incoming.get("borough") or "").strip().upper()
    candidate_list = list(candidates)

    if not candidate_list:
        return None, 0.0, "no_candidates"

    for candidate in candidate_list:
        candidate_name = (
            candidate.get("name") or candidate.get("name_normalized") or ""
        ).upper()
        candidate_zip = (candidate.get("zip_code") or "").strip()[:5]
        exact_key_in = build_address_key(
            incoming.get("building", ""),
            incoming.get("street", ""),
            incoming_zip,
        )
        exact_key_candidate = build_address_key(
            candidate.get("building", ""),
            candidate.get("street", ""),
            candidate_zip,
        )

        if (
            incoming_name
            and exact_key_in == exact_key_candidate
            and incoming_name == candidate_name
        ):
            return candidate, 1.0, "exact_name_address_match"

    stage_one = []
    for candidate in candidate_list:
        if not incoming_street:
            continue
        if _same_or_close_zip(
            incoming_zip, candidate.get("zip_code", "")
        ) and _normalize_for_match(candidate.get("street")).startswith(
            incoming_street[:5]
        ):
            score = score_match(incoming, candidate)
            if score >= threshold:
                stage_one.append((score, candidate))

    if stage_one:
        stage_one.sort(key=lambda item: item[0], reverse=True)
        return stage_one[0][1], stage_one[0][0], "zip_address_fuzzy"

    stage_two = []
    for candidate in candidate_list:
        score = score_match(incoming, candidate)
        candidate_borough = (candidate.get("borough") or "").strip().upper()
        if score >= 0.8 and (
            incoming_borough == candidate_borough
            or _same_or_close_zip(incoming_zip, candidate.get("zip_code", ""))
        ):
            stage_two.append((score, candidate))

    if stage_two:
        stage_two.sort(key=lambda item: item[0], reverse=True)
        return stage_two[0][1], stage_two[0][0], "name_zip_borough_fuzzy"

    best_match: Optional[Dict] = None
    best_score = 0.0
    for candidate in candidate_list:
        score = score_match(incoming, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return best_match, best_score, "fallback_fuzzy"
    return None, best_score, "no_match"
