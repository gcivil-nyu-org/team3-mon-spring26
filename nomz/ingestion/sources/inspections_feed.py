from __future__ import annotations

from typing import Dict, Iterable
from datetime import datetime

from nomz.ingestion.sources.nyc_endpoints import INSPECTIONS
from nomz.ingestion.utils.normalization import (
    first_non_empty,
    normalize_text,
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


def _parse_int(raw: object) -> int:
    raw_text = to_str(raw)
    if not raw_text:
        return 0
    try:
        return int(float(raw_text))
    except (ValueError, TypeError):
        return 0


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
            return datetime.strptime(raw_value[:len(fmt)], fmt).date().isoformat()
        except ValueError:
            continue
    return raw_value[:10] if len(raw_value) >= 10 else ""


def _critical_flag_to_int(raw: object) -> int:
    if to_str(raw).strip().upper() in {"Y", "YES", "TRUE", "1", "T"}:
        return 1
    return 0


def normalize_inspection_row(row: Dict) -> Dict:
    name = first_non_empty(row, ["dba", "business_name", "name"])
    street = first_non_empty(row, ["street", "address"])
    zip_code = first_non_empty(row, ["zipcode", "zip"])
    borough = first_non_empty(row, ["boro", "borough"])

    inspection_date = _parse_date(first_non_empty(row, ["inspection_date", "record_date"]))
    grade = _normalize_grade(first_non_empty(row, ["grade", "inspection_grade"]))
    score = _parse_score(first_non_empty(row, ["score"]))
    critical_count = _critical_flag_to_int(first_non_empty(row, ["critical_flag", "critical"]))
    violation_text = first_non_empty(row, ["violation_description", "violation"])

    camis = first_non_empty(row, ["camis", "camis_id"])
    inspection_key = "|".join([x for x in [camis, inspection_date, grade, score.__str__() if score is not None else ""] if x])

    return {
        "source": "DOHMH",
        "source_external_id": camis or inspection_key or first_non_empty(row, ["violation_code", "restaurant_id"]),
        "name": name,
        "name_normalized": normalize_text(name),
        "building": "",
        "street": street,
        "zip_code": zip_code,
        "borough": borough,
        "inspection_date": inspection_date,
        "grade": grade,
        "score": score,
        "critical_violations": critical_count,
        "noncritical_violations": 1 if violation_text and not critical_count else 0,
        "violation_description": violation_text,
        "inspection_key": inspection_key,
        "raw_payload": row,
    }


def stream_inspection_rows(client) -> Iterable[Dict]:
    for row in client.fetch_all(INSPECTIONS):
        normalized = normalize_inspection_row(row)
        if not normalized["name"]:
            continue
        yield normalized
