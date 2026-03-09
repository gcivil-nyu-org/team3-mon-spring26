from __future__ import annotations

from typing import Dict, Iterable

from nomz.ingestion.sources.nyc_endpoints import EATERIES
from nomz.ingestion.utils.normalization import first_non_empty, normalize_text, to_decimal_str, to_str, split_list_fields

def normalize_eateries_row(row: Dict) -> Dict:
    name = to_str(row.get("dba"))
    street = to_str(row.get("street"))
    building = to_str(row.get("building"))
    zip_code = to_str(row.get("zipcode") or row.get("zip"))
    borough = to_str(row.get("boro"))
    phone = to_str(row.get("phone"))

    lat = to_decimal_str(row.get("latitude"))
    lon = to_decimal_str(row.get("longitude"))
    cuisines = split_list_fields(row.get("cuisine_description"))

    return {
        "source": "EATERIES",
        "source_external_id": to_str(row.get("camis")) or to_str(row.get("dba")),
        "name": name,
        "name_normalized": normalize_text(name),
        "building": building,
        "street": street,
        "zip_code": zip_code,
        "borough": borough,
        "phone": phone,
        "website": to_str(row.get("website")),
        "latitude": lat,
        "longitude": lon,
        "cuisine_tags": cuisines,
        "raw_payload": row,
    }


def stream_eateries_rows(client) -> Iterable[Dict]:
    for row in client.fetch_all(EATERIES):
        normalized = normalize_eateries_row(row)
        if not normalized["name"]:
            continue
        if first_non_empty(normalized, ["name", "street", "zip_code"]):
            yield normalized
