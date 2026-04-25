from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable

from nomz.ingestion.sources.nyc_endpoints import INSPECTIONS
from nomz.ingestion.utils.normalization import (
    first_non_empty,
    normalize_text,
    sanitize_nyc_coordinate_pair,
    split_list_fields,
    to_str,
)


def _parse_score(raw: object) -> int | None:
    raw_text = to_str(raw)
    if not raw_text:
        return None
    try:
        return int(float(raw_text))
    except (ValueError, TypeError):
        return None


def _normalize_grade(raw: object) -> str:
    grade = to_str(raw).upper()
    if not grade:
        return ""
    return grade


def _parse_date(raw: object) -> str:
    raw_value = to_str(raw)
    if not raw_value:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw_value[: len(fmt)], fmt).date().isoformat()
        except ValueError:
            continue
    return raw_value[:10] if len(raw_value) >= 10 else ""


def _critical_flag_to_int(raw: object) -> int:
    normalized = to_str(raw).strip().upper()
    if normalized in {"Y", "YES", "TRUE", "1", "T", "CRITICAL"}:
        return 1
    return 0


def _noncritical_flag_to_int(raw: object, has_violation: bool) -> int:
    normalized = to_str(raw).strip().upper()
    if normalized in {"Y", "YES", "TRUE", "1", "T", "CRITICAL"}:
        return 0
    if normalized in {"NOT CRITICAL", "NOT_CRITICAL", "N", "NO", "FALSE", "0"}:
        return 1
    if normalized in {"NOT APPLICABLE", "N/A", ""}:
        return 0
    return 1 if has_violation else 0


def _inspection_group_key(
    camis: str, inspection_date: str, inspection_type: str, action: str
) -> str:
    return "|".join(
        [camis or "", inspection_date or "", inspection_type or "", action or ""]
    )


def normalize_inspection_row(row: Dict) -> Dict:
    name = first_non_empty(row, ["dba", "business_name", "name"])
    street = first_non_empty(row, ["street", "address"])
    building = first_non_empty(row, ["building", "house_number"])
    zip_code = first_non_empty(row, ["zipcode", "zip"])
    borough = first_non_empty(row, ["boro", "borough"])
    phone = first_non_empty(row, ["phone", "phone_number"])
    latitude, longitude = sanitize_nyc_coordinate_pair(
        first_non_empty(row, ["latitude"]),
        first_non_empty(row, ["longitude"]),
    )
    cuisine_tags = split_list_fields(
        first_non_empty(row, ["cuisine_description", "cuisine"])
    )

    inspection_date = _parse_date(
        first_non_empty(row, ["inspection_date", "record_date"])
    )
    inspection_type = first_non_empty(row, ["inspection_type"])
    action = first_non_empty(row, ["action"])
    grade = _normalize_grade(first_non_empty(row, ["grade", "inspection_grade"]))
    score = _parse_score(first_non_empty(row, ["score"]))
    critical_flag = first_non_empty(row, ["critical_flag", "critical"])
    violation_text = first_non_empty(row, ["violation_description", "violation"])
    has_violation = bool(to_str(violation_text).strip())
    critical_count = _critical_flag_to_int(critical_flag)
    noncritical_count = _noncritical_flag_to_int(critical_flag, has_violation)

    camis = first_non_empty(row, ["camis", "camis_id"])
    inspection_key = _inspection_group_key(
        camis=camis,
        inspection_date=inspection_date,
        inspection_type=inspection_type,
        action=action,
    )

    return {
        "source": "DOHMH",
        "source_external_id": camis
        or inspection_key
        or first_non_empty(row, ["violation_code", "restaurant_id"]),
        "name": name,
        "name_normalized": normalize_text(name),
        "building": building,
        "street": street,
        "zip_code": zip_code,
        "borough": borough,
        "phone": phone,
        "website": "",
        "latitude": latitude,
        "longitude": longitude,
        "cuisine_tags": cuisine_tags,
        "inspection_date": inspection_date,
        "inspection_type": inspection_type,
        "action": action,
        "grade": grade,
        "score": score,
        "critical_violations": critical_count,
        "noncritical_violations": noncritical_count,
        "violation_count": 1 if has_violation else 0,
        "violation_description": [violation_text] if has_violation else [],
        "inspection_key": inspection_key,
        "raw_payload": row,
    }


def _merge_inspection_records(base: Dict, row: Dict) -> None:
    if not base.get("building"):
        base["building"] = row.get("building") or ""
    if not base.get("street"):
        base["street"] = row.get("street") or ""
    if not base.get("zip_code"):
        base["zip_code"] = row.get("zip_code") or ""
    if not base.get("borough"):
        base["borough"] = row.get("borough") or ""
    if not base.get("phone"):
        base["phone"] = row.get("phone") or ""
    if not base.get("latitude"):
        base["latitude"] = row.get("latitude")
    if not base.get("longitude"):
        base["longitude"] = row.get("longitude")

    if row.get("grade") and not base.get("grade"):
        base["grade"] = row["grade"]
    if row.get("score") is not None and base.get("score") is None:
        base["score"] = row["score"]
    if row.get("inspection_type") and not base.get("inspection_type"):
        base["inspection_type"] = row["inspection_type"]
    if row.get("action") and not base.get("action"):
        base["action"] = row["action"]

    base["critical_violations"] = int(base.get("critical_violations") or 0) + int(
        row.get("critical_violations") or 0
    )
    base["noncritical_violations"] = int(base.get("noncritical_violations") or 0) + int(
        row.get("noncritical_violations") or 0
    )
    base["violation_count"] = int(base.get("violation_count") or 0) + int(
        row.get("violation_count") or 0
    )

    existing_violations = list(base.get("violation_description") or [])
    existing_set = set(existing_violations)
    for text in row.get("violation_description") or []:
        if text and text not in existing_set:
            existing_violations.append(text)
            existing_set.add(text)
    base["violation_description"] = existing_violations

    existing_tags = list(base.get("cuisine_tags") or [])
    existing_tags_set = set(existing_tags)
    for tag in row.get("cuisine_tags") or []:
        if tag and tag not in existing_tags_set:
            existing_tags.append(tag)
            existing_tags_set.add(tag)
    base["cuisine_tags"] = existing_tags

    payload = base.get("raw_payload")
    if isinstance(payload, list):
        payload.append(row.get("raw_payload"))
    else:
        base["raw_payload"] = [payload, row.get("raw_payload")]


def stream_inspection_rows(client) -> Iterable[Dict]:
    current_key = None
    current_record = None
    for row in client.fetch_all(
        INSPECTIONS,
        limit=500,
        order_by="camis,inspection_date,inspection_type,action",
    ):
        normalized = normalize_inspection_row(row)
        if not normalized["name"] or not normalized["inspection_key"]:
            continue

        inspection_key = normalized["inspection_key"]
        if inspection_key != current_key:
            if current_record is not None:
                yield current_record
            current_key = inspection_key
            current_record = normalized
            continue

        _merge_inspection_records(current_record, normalized)

    if current_record is not None:
        yield current_record
