from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha1
from typing import Any, Dict, Iterable, Optional

from django.db import transaction
from django.utils import timezone

from nomz.ingestion.utils.normalization import normalize_text
from nomz.ingestion.utils.resolver import resolve_restaurant
from nomz.ingestion.utils.score import compute_composite_score_from_records
from nomz.models import (
    DataIngestionRun,
    DiningOutLocation,
    InspectionRecord,
    Restaurant,
    RestaurantSourceRecord,
)


def _to_decimal(value: object) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _zip_prefix(zip_code: str | None) -> str:
    if not zip_code:
        return ""
    return str(zip_code).strip()[:5]


def _record_to_match_payload(restaurant: Restaurant) -> Dict[str, Any]:
    return {
        "id": str(restaurant.id),
        "name": restaurant.name or "",
        "name_normalized": restaurant.name_normalized or "",
        "building": restaurant.building or "",
        "street": restaurant.street or "",
        "zip_code": restaurant.zip_code or "",
        "borough": restaurant.borough or "",
        "latitude": str(restaurant.latitude) if restaurant.latitude is not None else "",
        "longitude": str(restaurant.longitude) if restaurant.longitude is not None else "",
    }


def _normalize_source_record_id(source: str, row: Dict[str, Any]) -> str:
    if row.get("source_external_id"):
        return str(row["source_external_id"])

    seed = "|".join(
        [
            source,
            str(row.get("name") or ""),
            str(row.get("street") or ""),
            str(row.get("zip_code") or ""),
            str(row.get("borough") or ""),
            str(row.get("latitude") or ""),
            str(row.get("longitude") or ""),
        ]
    )
    return sha1(seed.encode("utf-8")).hexdigest()


def _normalize_inspection_key(row: Dict[str, Any], restaurant_id: int) -> str:
    if row.get("inspection_key"):
        return str(row["inspection_key"])

    parts = [
        str(restaurant_id),
        str(row.get("inspection_date") or ""),
        str(row.get("grade") or ""),
        str(row.get("score") if row.get("score") is not None else ""),
        str(row.get("critical_violations") if row.get("critical_violations") is not None else ""),
        str(row.get("noncritical_violations") if row.get("noncritical_violations") is not None else ""),
        str(row.get("violation_description") or row.get("violation") or ""),
    ]
    return sha1("|".join(parts).encode("utf-8")).hexdigest()


@dataclass
class IngestionStats:
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_matched: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    source_breakdown: dict[str, int] = None

    def __post_init__(self):
        if self.source_breakdown is None:
            self.source_breakdown = defaultdict(int)


class DbIngestionWriter:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = IngestionStats()

    def ingest(self, record: Dict[str, Any]) -> None:
        source = record.get("source", "")
        if not source:
            self.stats.records_failed += 1
            return

        self.stats.source_breakdown[source] += 1
        self.stats.records_processed += 1

        try:
            if source == "DOHMH":
                self._handle_inspection_record(record)
            else:
                self._handle_restaurant_source_record(record)
        except Exception:
            self.stats.records_failed += 1
            raise

    def _handle_restaurant_source_record(self, record: Dict[str, Any]) -> None:
        with transaction.atomic():
            restaurant = self._resolve_restaurant(record)
            if not restaurant:
                self.stats.records_skipped += 1
                return

            source_id = _normalize_source_record_id(record.get("source", ""), record)
            if self.dry_run:
                return

            existing = RestaurantSourceRecord.objects.filter(
                source=record["source"],
                external_id=source_id,
            ).first()
            payload = {
                "restaurant": restaurant,
                "source": record["source"],
                "external_id": source_id,
                "external_name": record.get("name", ""),
                "external_address": self._format_address(record),
                "raw_payload": record.get("raw_payload"),
                "confidence": record.get("match_confidence", 1.0),
            }

            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                existing.last_seen_at = timezone.now()
                existing.save(update_fields=[
                    "restaurant",
                    "source",
                    "external_id",
                    "external_name",
                    "external_address",
                    "raw_payload",
                    "confidence",
                    "last_seen_at",
                ])
                self.stats.records_updated += 1
            else:
                RestaurantSourceRecord.objects.create(**payload)
                self.stats.records_created += 1

            if record.get("source") == "DINING_OUT":
                self._upsert_dining_out_profile(restaurant, record)

    def _handle_inspection_record(self, record: Dict[str, Any]) -> None:
        restaurant = self._resolve_restaurant(record)
        if not restaurant:
            self.stats.records_skipped += 1
            return

        inspection_date = self._coerce_date(record.get("inspection_date"))
        if inspection_date is None:
            self.stats.records_skipped += 1
            return

        if self.dry_run:
            return

        inspection_key = _normalize_inspection_key(record, restaurant.id)
        defaults = {
            "inspection_date": inspection_date,
            "grade": (record.get("grade") or "").strip().upper() or None,
            "score": self._coerce_int(record.get("score")),
            "critical_violations": self._coerce_int(record.get("critical_violations")),
            "noncritical_violations": self._coerce_int(record.get("noncritical_violations")),
            "violation_count": self._coerce_int(record.get("violation_count")) or self._coerce_int(record.get("critical_violations")) + self._coerce_int(record.get("noncritical_violations")),
            "inspection_type": record.get("inspection_type"),
            "action": record.get("action"),
            "violations": self._coerce_violations(record.get("violation_description") or record.get("violations")),
            "camis": record.get("source_external_id"),
            "boro": record.get("borough") or record.get("boro"),
            "raw_payload": record.get("raw_payload"),
        }

        inspection, created = InspectionRecord.objects.get_or_create(
            restaurant=restaurant,
            inspection_key=inspection_key,
            defaults=defaults,
        )
        if not created:
            for key, value in defaults.items():
                setattr(inspection, key, value)
            inspection.save()
            self.stats.records_updated += 1
        else:
            self.stats.records_created += 1

        self._refresh_restaurant_score(restaurant)

    def _resolve_restaurant(self, record: Dict[str, Any]) -> Optional[Restaurant]:
        name_normalized = normalize_text(record.get("name") or "")
        if not name_normalized:
            return None

        zip_code = str(record.get("zip_code") or "").strip()
        street = str(record.get("street") or "").strip()

        candidates = Restaurant.objects.filter(is_active=True)
        if zip_code:
            candidates = candidates.filter(zip_code__startswith=_zip_prefix(zip_code))
        if not candidates.exists() and street:
            candidates = Restaurant.objects.filter(is_active=True, street__iexact=street)
        if not candidates.exists():
            candidates = Restaurant.objects.filter(is_active=True)

        candidate_payloads = [_record_to_match_payload(item) for item in candidates]
        matched, score, strategy = resolve_restaurant(record, candidate_payloads)
        record["match_confidence"] = score
        record["match_strategy"] = strategy

        if not matched:
            normalized_payload = {
                "name": record.get("name") or "",
                "display_name": record.get("name") or "",
                "name_normalized": name_normalized,
                "building": str(record.get("building") or "") or None,
                "street": str(record.get("street") or "") or None,
                "borough": str(record.get("borough") or "") or None,
                "zip_code": _zip_prefix(zip_code) if zip_code else None,
                "phone": str(record.get("phone") or "") or None,
                "website": str(record.get("website") or "") or None,
                "cuisine_tags": list(record.get("cuisine_tags") or []),
                "latitude": _to_decimal(record.get("latitude")),
                "longitude": _to_decimal(record.get("longitude")),
            }

            if self.dry_run:
                self.stats.records_created += 1
                return Restaurant(**normalized_payload)

            restaurant = Restaurant.objects.create(**normalized_payload)
            self.stats.records_created += 1
            self.stats.records_matched += 1
            return restaurant

        self.stats.records_matched += 1
        self.stats.records_updated += 1

        restaurant = Restaurant.objects.get(id=int(matched["id"]))
        changed = False

        if self.dry_run:
            return restaurant

        if not restaurant.name_normalized:
            restaurant.name_normalized = name_normalized
            changed = True

        if not restaurant.display_name and record.get("name"):
            restaurant.display_name = record["name"]
            changed = True

        if (not restaurant.street or not restaurant.street.strip()) and street:
            restaurant.street = street
            changed = True

        if (not restaurant.zip_code or not restaurant.zip_code.strip()) and zip_code:
            restaurant.zip_code = zip_code
            changed = True

        if not restaurant.building and record.get("building"):
            restaurant.building = str(record.get("building") or "").strip()
            changed = True

        if not restaurant.latitude and record.get("latitude"):
            restaurant.latitude = _to_decimal(record.get("latitude"))
            changed = True

        if not restaurant.longitude and record.get("longitude"):
            restaurant.longitude = _to_decimal(record.get("longitude"))
            changed = True

        incoming_cuisines = record.get("cuisine_tags") or []
        merged_cuisines = list({*(restaurant.cuisine_tags or []), *incoming_cuisines})
        if set(merged_cuisines) != set(restaurant.cuisine_tags or []):
            restaurant.cuisine_tags = merged_cuisines
            changed = True

        if changed:
            restaurant.save()

        return restaurant

    def _upsert_dining_out_profile(self, restaurant: Restaurant, record: Dict[str, Any]) -> None:
        metadata = record.get("dining_out_metadata") or {}
        if not metadata:
            return

        defaults = {
            "license_type": metadata.get("license_type"),
            "license_status": metadata.get("license_status"),
            "license_issue_date": self._coerce_date(metadata.get("license_issue_date")),
            "license_expiration_date": self._coerce_date(metadata.get("license_expiration_date")),
            "location_type": (metadata.get("location_type") or "UNKNOWN").lower()[:20],
            "building_number": metadata.get("building_number"),
            "council_district": metadata.get("council_district"),
            "community_board": metadata.get("community_board"),
            "nta2020": metadata.get("nta2020"),
            "bin": metadata.get("bin"),
            "bbl": metadata.get("bbl"),
            "capacity_estimate": self._coerce_int(metadata.get("capacity_estimate")),
        }

        DiningOutLocation.objects.update_or_create(
            restaurant=restaurant,
            defaults=defaults,
        )

    def _refresh_restaurant_score(self, restaurant: Restaurant) -> None:
        if self.dry_run:
            return

        latest = restaurant.inspections.order_by("-inspection_date", "-id").first()
        score_data = compute_composite_score_from_records([latest] if latest else [])

        restaurant.composite_score = score_data["composite_score"]
        restaurant.grade_latest = score_data["grade"]
        restaurant.grade_score_latest = score_data["grade_score"]
        restaurant.last_inspection_date = score_data["last_inspection_date"]
        restaurant.composite_score_calculated_at = timezone.now()
        restaurant.save()

    def _coerce_date(self, value: object) -> Optional[datetime.date]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if hasattr(value, "date") and hasattr(value, "day"):
            return value.date()

        value_text = str(value).strip()
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%m/%d/%Y"]:
            try:
                return datetime.strptime(value_text[:len(fmt)], fmt).date()
            except ValueError:
                continue
        return None

    def _coerce_int(self, value: object) -> int:
        if value in (None, ""):
            return 0
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def _coerce_violations(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        value_text = str(value).strip()
        if not value_text:
            return []
        return [value_text]

    def _format_address(self, record: Dict[str, Any]) -> str:
        parts = [
            str(record.get("building") or "").strip(),
            str(record.get("street") or "").strip(),
            str(record.get("zip_code") or "").strip(),
        ]
        return ", ".join(part for part in parts if part)


class IngestionRunContext:
    def __init__(self, dataset: str):
        self.dataset = dataset
        self.run = DataIngestionRun.objects.create(dataset=dataset)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.run.finished_at = timezone.now()
        if exc_type is not None:
            self.run.status = "failed"
        else:
            self.run.status = "success"
        self.run.save(update_fields=["status", "finished_at"])
        return False

    def set_summary(
        self,
        stats: IngestionStats,
        errors: Optional[Dict[str, str]] = None,
        status: Optional[str] = None,
    ):
        if status in {"running", "success", "failed"}:
            self.run.status = status
        self.run.records_fetched = stats.records_processed
        self.run.records_processed = stats.records_processed
        self.run.records_created = stats.records_created
        self.run.records_updated = stats.records_updated
        self.run.records_matched = stats.records_matched
        self.run.records_skipped = stats.records_skipped
        self.run.error_count = stats.records_failed
        if errors:
            self.run.error_log = [f"{key}: {value}" for key, value in errors.items()]
        else:
            self.run.error_log = []
        self.run.save()
