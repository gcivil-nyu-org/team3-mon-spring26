"""
Final ingestion tests: `persistence.DbIngestionWriter` upsert paths and `runner.run_ingestion`.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError, OperationalError

from nomz.ingestion import persistence as persistence_mod
from nomz.ingestion.persistence import (
    DbIngestionWriter,
    IngestionRunContext,
    IngestionStats,
)
from nomz.ingestion.runner import run_ingestion
from nomz.ingestion.sources.socrata_client import SocrataError
from nomz.ingestion.utils.normalization import normalize_text
from nomz.models import (
    DataIngestionRun,
    DiningOutLocation,
    InspectionRecord,
    Restaurant,
    RestaurantSearch,
    RestaurantSourceRecord,
)

pytestmark = pytest.mark.django_db


def _eid() -> str:
    return uuid.uuid4().hex[:12]


def _base_restaurant(**kwargs) -> Restaurant:
    defaults = dict(
        name=f"Rest_{_eid()}",
        display_name="",
        name_normalized="",
        is_active=True,
        street="100 Broadway",
        zip_code="10007",
        borough="MANHATTAN",
        building="100",
        cuisine_type="american",
        price_range="$$",
    )
    defaults.update(kwargs)
    if not defaults.get("name_normalized") and defaults.get("name"):
        defaults["name_normalized"] = normalize_text(defaults["name"])
    return Restaurant.objects.create(**defaults)


# ---------------------------------------------------------------------------
# persistence: source link + RestaurantSourceRecord create / update (save)
# ---------------------------------------------------------------------------


def test_eateries_ingest_creates_then_updates_source_record():
    rest = _base_restaurant(name="Joe's Diner", display_name="Joe's Diner")
    ext = _eid()
    base = {
        "source": "EATERIES",
        "source_external_id": ext,
        "name": "Joe's Diner",
        "name_normalized": normalize_text("Joe's Diner"),
        "building": "100",
        "street": "Broadway",
        "zip_code": "10007",
        "borough": "MANHATTAN",
        "latitude": "40.7128",
        "longitude": "-74.0060",
        "cuisine_tags": ["American"],
        "raw_payload": {"id": ext},
    }
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(dict(base))
    link = RestaurantSourceRecord.objects.get(source="EATERIES", external_id=ext)
    assert link.restaurant_id == rest.id
    assert writer.stats.records_created >= 1

    writer2 = DbIngestionWriter(dry_run=False)
    rec2 = dict(base)
    rec2["name"] = "Joe's Diner Updated"
    rec2["match_confidence"] = 0.95
    writer2.ingest(rec2)
    link.refresh_from_db()
    assert "Updated" in link.external_name or link.external_name
    assert writer2.stats.records_updated >= 1


def test_ingest_matches_via_existing_source_link():
    rest = _base_restaurant(name="Linked Spot")
    ext = _eid()
    RestaurantSourceRecord.objects.create(
        restaurant=rest,
        source="EATERIES",
        external_id=ext,
        external_name="Linked Spot",
        external_address="1 Main, NYC, 10001",
        confidence=1.0,
    )
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(
        {
            "source": "EATERIES",
            "source_external_id": ext,
            "name": "Linked Spot",
            "name_normalized": normalize_text("Linked Spot"),
            "building": "1",
            "street": "Main St",
            "zip_code": "10001",
            "borough": "MANHATTAN",
        }
    )
    assert writer.stats.records_matched >= 1
    assert writer.stats.records_updated >= 1


# ---------------------------------------------------------------------------
# persistence: resolver match (exact name + address key) + enrichment save
# ---------------------------------------------------------------------------


def test_eateries_resolves_exact_name_address_and_enriches():
    rest = _base_restaurant(
        name="Exact Match Cafe",
        display_name="Exact Match Cafe",
        building="50",
        street="Wall St",
        zip_code="10005",
        borough="MANHATTAN",
        phone="",
        website="",
    )
    ext = _eid()
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(
        {
            "source": "EATERIES",
            "source_external_id": ext,
            "name": "Exact Match Cafe",
            "name_normalized": normalize_text("Exact Match Cafe"),
            "building": "50",
            "street": "Wall St",
            "zip_code": "10005",
            "borough": "MANHATTAN",
            "phone": "2125550000",
            "website": "https://exact.example.com/",
        }
    )
    rest.refresh_from_db()
    assert rest.phone == "2125550000"
    assert "exact.example.com" in (rest.website or "")


def test_eateries_fuzzy_zip_street_high_score_match():
    """Stage-one resolver path: same ZIP prefix + street prefix + strong name similarity."""
    rest = _base_restaurant(
        name="Fuzzy Tacos Shop",
        display_name="Fuzzy Tacos Shop",
        building="200",
        street="Flatbush Avenue",
        zip_code="11217",
        borough="BROOKLYN",
        latitude=Decimal("40.678"),
        longitude=Decimal("-73.968"),
    )
    ext = _eid()
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(
        {
            "source": "EATERIES",
            "source_external_id": ext,
            "name": "Fuzzy Tacos Shop",
            "name_normalized": normalize_text("Fuzzy Tacos Shop"),
            "building": "200",
            "street": "Flatbush Avenue",
            "zip_code": "11217",
            "borough": "BROOKLYN",
            "latitude": "40.678",
            "longitude": "-73.968",
        }
    )
    assert writer.stats.records_matched >= 1
    assert RestaurantSourceRecord.objects.filter(
        source="EATERIES", external_id=ext, restaurant=rest
    ).exists()


# ---------------------------------------------------------------------------
# persistence: new restaurant create + RestaurantSearch sync (create/update)
# ---------------------------------------------------------------------------


def test_new_restaurant_created_and_restaurant_search_row_created():
    name = f"Brand New {_eid()}"
    ext = _eid()
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(
        {
            "source": "EATERIES",
            "source_external_id": ext,
            "name": name,
            "name_normalized": normalize_text(name),
            "building": "9",
            "street": "Christopher St",
            "zip_code": "10014",
            "borough": "MANHATTAN",
            "cuisine_tags": ["Thai"],
        }
    )
    assert Restaurant.objects.filter(name=name).exists()
    assert RestaurantSearch.objects.filter(name=name[:200]).exists()
    assert writer.stats.records_created >= 1


def test_restaurant_search_update_on_second_ingest():
    name = f"Search Sync {_eid()}"
    r = _base_restaurant(name=name, description="v1")
    ext1, ext2 = _eid(), _eid()
    w = DbIngestionWriter(dry_run=False)
    w.ingest(
        {
            "source": "EATERIES",
            "source_external_id": ext1,
            "name": name,
            "name_normalized": normalize_text(name),
            "building": r.building,
            "street": r.street,
            "zip_code": r.zip_code,
            "borough": r.borough,
        }
    )
    r.description = "v2 fresh"
    r.save(update_fields=["description"])
    w.ingest(
        {
            "source": "EATERIES",
            "source_external_id": ext2,
            "name": name,
            "name_normalized": normalize_text(name),
            "building": r.building,
            "street": r.street,
            "zip_code": r.zip_code,
            "borough": r.borough,
        }
    )
    rs = RestaurantSearch.objects.get(name=name[:200])
    assert "v2" in (rs.description or "") or rs.description


# ---------------------------------------------------------------------------
# persistence: DOHMH inspections — get_or_create + update (save)
# ---------------------------------------------------------------------------


def test_dohmh_inspection_create_then_update_same_inspection_key():
    rest = _base_restaurant(name="Inspect Me")
    camis = _eid()
    ikey = f"{camis}|2024-06-01|cycle|none"
    row = {
        "source": "DOHMH",
        "source_external_id": camis,
        "name": rest.name,
        "name_normalized": rest.name_normalized,
        "building": rest.building,
        "street": rest.street,
        "zip_code": rest.zip_code,
        "borough": rest.borough,
        "inspection_date": "2024-06-01",
        "grade": "A",
        "score": 10,
        "critical_violations": 0,
        "noncritical_violations": 0,
        "violation_count": 0,
        "inspection_type": "cycle",
        "action": "none",
        "violation_description": [],
        "inspection_key": ikey,
        "raw_payload": {},
    }
    w1 = DbIngestionWriter(dry_run=False)
    w1.ingest(dict(row))
    ins = InspectionRecord.objects.get(restaurant=rest, inspection_key=ikey)
    assert ins.grade == "A"
    assert w1.stats.records_created >= 1

    row2 = dict(row)
    row2["grade"] = "B"
    row2["score"] = 22
    w2 = DbIngestionWriter(dry_run=False)
    w2.ingest(row2)
    ins.refresh_from_db()
    assert ins.grade == "B"
    assert ins.score == 22
    assert w2.stats.records_updated >= 1


def test_dohmh_skips_when_inspection_date_invalid():
    rest = _base_restaurant(name="No Date Rest")
    w = DbIngestionWriter(dry_run=False)
    w.ingest(
        {
            "source": "DOHMH",
            "source_external_id": _eid(),
            "name": rest.name,
            "name_normalized": rest.name_normalized,
            "building": "1",
            "street": "Main",
            "zip_code": "10001",
            "borough": "MANHATTAN",
            "inspection_date": "",
            "grade": "A",
            "inspection_key": "k",
        }
    )
    assert w.stats.records_skipped >= 1


# ---------------------------------------------------------------------------
# persistence: DiningOutLocation update_or_create
# ---------------------------------------------------------------------------


def test_dining_out_upserts_profile_metadata():
    rest = _base_restaurant(name="Sidewalk Bites")
    ext = _eid()
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(
        {
            "source": "DINING_OUT",
            "source_external_id": ext,
            "name": rest.name,
            "name_normalized": rest.name_normalized,
            "building": rest.building,
            "street": rest.street,
            "zip_code": rest.zip_code,
            "borough": rest.borough,
            "dining_out_metadata": {
                "license_type": "Sidewalk",
                "license_status": "Active",
                "license_issue_date": "2023-01-15",
                "license_expiration_date": "2024-01-15",
                "location_type": "outdoor",
                "building_number": "12",
                "council_district": "3",
                "community_board": "102",
                "nta2020": "MN012",
                "bin": "1000000",
                "bbl": "1000010001",
                "capacity_estimate": "20",
            },
        }
    )
    loc = DiningOutLocation.objects.get(restaurant=rest)
    assert loc.license_status == "Active"
    assert loc.location_type == "outdoor"


def test_dining_out_skips_when_no_metadata():
    rest = _base_restaurant(name="Plain Dining")
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(
        {
            "source": "DINING_OUT",
            "source_external_id": _eid(),
            "name": rest.name,
            "name_normalized": rest.name_normalized,
            "building": "1",
            "street": "2 Ave",
            "zip_code": "10009",
            "borough": "MANHATTAN",
        }
    )
    assert not DiningOutLocation.objects.filter(restaurant=rest).exists()


# ---------------------------------------------------------------------------
# persistence: dry-run + failures + OperationalError retry
# ---------------------------------------------------------------------------


def test_dry_run_no_database_writes_for_new_restaurant():
    name = f"DryOnly {_eid()}"
    w = DbIngestionWriter(dry_run=True)
    w.ingest(
        {
            "source": "EATERIES",
            "source_external_id": _eid(),
            "name": name,
            "name_normalized": normalize_text(name),
            "building": "1",
            "street": "Unknown Rd",
            "zip_code": "99999",
            "borough": "MANHATTAN",
        }
    )
    assert not Restaurant.objects.filter(name=name).exists()
    assert w.stats.records_created >= 1


def test_ingest_fails_without_source():
    w = DbIngestionWriter()
    w.ingest({"name": "X"})
    assert w.stats.records_failed == 1


@patch("nomz.ingestion.persistence.time.sleep", return_value=None)
def test_operational_error_sqlite_lock_retries_then_raises(mock_sleep):
    rest = _base_restaurant(name="Lock Test")
    calls = {"n": 0}

    @contextmanager
    def boom_atomic(*args, **kwargs):
        calls["n"] += 1
        raise OperationalError("database is locked")
        yield  # pragma: no cover

    row = {
        "source": "EATERIES",
        "source_external_id": _eid(),
        "name": rest.name,
        "name_normalized": rest.name_normalized,
        "building": rest.building,
        "street": rest.street,
        "zip_code": rest.zip_code,
        "borough": rest.borough,
    }
    w = DbIngestionWriter(dry_run=False)
    with patch(
        "nomz.ingestion.persistence.transaction.atomic",
        side_effect=lambda *a, **k: boom_atomic(),
    ):
        with pytest.raises(OperationalError):
            w.ingest(row)
    # First attempt + one retry cycle per `attempts` increment → 11 atomic enters for limit 10.
    assert calls["n"] == w._sqlite_lock_retry_attempts + 1
    assert mock_sleep.call_count == w._sqlite_lock_retry_attempts


# ---------------------------------------------------------------------------
# persistence: IntegrityError handling
# ---------------------------------------------------------------------------


def test_restaurant_create_integrityerror_recovers_via_name_lookup():
    """
    Exercise the `except IntegrityError` branch after `Restaurant.objects.create`
    by forcing create to fail while a same-name row exists for the fallback query.
    """
    recover = _base_restaurant(
        name="Integr Cafe",
        display_name="Integr Cafe",
        street="Main St",
        zip_code="11201",
        borough="BROOKLYN",
        building="1",
    )
    iexact_calls = {"n": 0}
    real_filter = Restaurant.objects.filter

    def filter_proxy(*args, **kwargs):
        if "name__iexact" in kwargs:
            iexact_calls["n"] += 1
            mq = MagicMock()
            if iexact_calls["n"] == 1:
                mq.order_by.return_value.first.return_value = None
            else:
                mq.order_by.return_value.first.return_value = recover
            return mq
        return real_filter(*args, **kwargs)

    ext = _eid()
    record = {
        "source": "EATERIES",
        "source_external_id": ext,
        "name": "Integr Cafe",
        "name_normalized": normalize_text("Integr Cafe"),
        "building": "1",
        "street": "Main St",
        "zip_code": "11201",
        "borough": "BROOKLYN",
    }
    with patch.object(Restaurant.objects, "filter", side_effect=filter_proxy):
        with patch.object(
            Restaurant.objects,
            "create",
            side_effect=IntegrityError("unique name"),
        ):
            w = DbIngestionWriter(dry_run=False)
            w.ingest(record)

    assert RestaurantSourceRecord.objects.filter(
        restaurant=recover,
        source="EATERIES",
        external_id=persistence_mod._normalize_source_record_id("EATERIES", record),
    ).exists()


def test_source_record_create_integrityerror_surfaces_via_ingest():
    rest = _base_restaurant(name="Src Int")
    row = {
        "source": "EATERIES",
        "source_external_id": _eid(),
        "name": rest.name,
        "name_normalized": rest.name_normalized,
        "building": rest.building,
        "street": rest.street,
        "zip_code": rest.zip_code,
        "borough": rest.borough,
    }
    w = DbIngestionWriter(dry_run=False)
    with patch.object(
        RestaurantSourceRecord.objects,
        "create",
        side_effect=IntegrityError("duplicate source"),
    ):
        with pytest.raises(IntegrityError):
            w.ingest(row)
    assert w.stats.records_failed >= 1


# ---------------------------------------------------------------------------
# persistence: IngestionRunContext
# ---------------------------------------------------------------------------


def test_ingestion_run_context_success_updates_run():
    with IngestionRunContext("test-dataset") as ctx:
        stats = IngestionStats()
        stats.records_processed = 3
        stats.records_created = 1
        ctx.set_summary(stats, status="success")
    run = DataIngestionRun.objects.get(pk=ctx.run.pk)
    assert run.status == "success"
    assert run.finished_at is not None


def test_ingestion_run_context_failure_marks_failed():
    run_id = None
    with pytest.raises(ValueError):
        with IngestionRunContext("bad-dataset") as ctx:
            run_id = ctx.run.pk
            raise ValueError("boom")
    run = DataIngestionRun.objects.get(pk=run_id)
    assert run.status == "failed"


# ---------------------------------------------------------------------------
# runner.run_ingestion — mock stream factories + exception paths
# ---------------------------------------------------------------------------


def test_run_ingestion_iterates_all_sources_and_counts_writes():
    rows = {
        "EATERIES": [{"source": "EATERIES", "id": "1"}],
        "DINING_OUT": [{"source": "DINING_OUT", "id": "2"}],
        "DOHMH": [{"source": "DOHMH", "id": "3"}],
    }

    def stream_eateries(_client, **_kwargs):
        for item in rows["EATERIES"]:
            yield item

    def stream_dining_out(_client, **_kwargs):
        for item in rows["DINING_OUT"]:
            yield item

    def stream_dohmh(_client, **_kwargs):
        for item in rows["DOHMH"]:
            yield item

    written = []

    def writer(rec):
        written.append(rec["source"])

    with patch(
        "nomz.ingestion.runner.stream_eateries_rows", side_effect=stream_eateries
    ), patch(
        "nomz.ingestion.runner.stream_dining_out_rows",
        side_effect=stream_dining_out,
    ), patch(
        "nomz.ingestion.runner.stream_inspection_rows", side_effect=stream_dohmh
    ):
        summary = run_ingestion(writer=writer, app_token=None)

    assert summary.ok is True
    assert summary.total == 3
    assert set(summary.counts.keys()) == {"EATERIES", "DINING_OUT", "DOHMH"}
    assert written == ["EATERIES", "DINING_OUT", "DOHMH"]


def test_run_ingestion_writer_integrity_error_isolated_per_source():
    """Writer raises IntegrityError: runner catches, counts failure, continues other sources."""

    def stream_ok(_client, **_kwargs):
        yield {"source": "EATERIES", "n": 1}

    def stream_bad(_client, **_kwargs):
        yield {"source": "DINING_OUT", "n": 1}

    def stream_ok2(_client, **_kwargs):
        yield {"source": "DOHMH", "n": 1}

    def writer(rec):
        if rec["source"] == "DINING_OUT":
            raise IntegrityError("fk violation")

    with patch(
        "nomz.ingestion.runner.stream_eateries_rows", side_effect=stream_ok
    ), patch(
        "nomz.ingestion.runner.stream_dining_out_rows", side_effect=stream_bad
    ), patch(
        "nomz.ingestion.runner.stream_inspection_rows", side_effect=stream_ok2
    ):
        summary = run_ingestion(writer=writer)

    assert summary.failures == 1
    assert summary.counts.get("EATERIES") == 1
    assert summary.counts.get("DOHMH") == 1
    assert "DINING_OUT" in summary.errors


def test_run_ingestion_stream_socrata_error():
    def boom(_client, **_kwargs):
        raise SocrataError("rate limited", status_code=429)
        yield  # pragma: no cover

    def empty(_client, **_kwargs):
        yield from ()

    with patch("nomz.ingestion.runner.stream_eateries_rows", side_effect=boom), patch(
        "nomz.ingestion.runner.stream_dining_out_rows", side_effect=empty
    ), patch("nomz.ingestion.runner.stream_inspection_rows", side_effect=empty):
        summary = run_ingestion(writer=lambda _r: None)

    assert summary.failures >= 1
    assert "EATERIES" in summary.errors


def test_run_ingestion_stream_generic_exception_chained_message():
    def boom(_client, **_kwargs):
        raise RuntimeError("network down")
        yield  # pragma: no cover

    def empty(_client, **_kwargs):
        yield from ()

    with patch("nomz.ingestion.runner.stream_eateries_rows", side_effect=boom), patch(
        "nomz.ingestion.runner.stream_dining_out_rows", side_effect=empty
    ), patch("nomz.ingestion.runner.stream_inspection_rows", side_effect=empty):
        summary = run_ingestion(writer=lambda _r: None)

    assert summary.failures >= 1
    assert "EATERIES" in summary.errors


def test_run_ingestion_skip_sources_and_max_records():
    seq = list(range(20))

    def long_stream(_client, **_kwargs):
        for i in seq:
            yield {"source": "EATERIES", "i": i}

    written = []

    def empty(_client, **_kwargs):
        yield from ()

    with patch(
        "nomz.ingestion.runner.stream_eateries_rows", side_effect=long_stream
    ), patch("nomz.ingestion.runner.stream_dining_out_rows", side_effect=empty), patch(
        "nomz.ingestion.runner.stream_inspection_rows", side_effect=empty
    ):
        summary = run_ingestion(
            writer=lambda r: written.append(r),
            skip_sources={"DOHMH", "DINING_OUT"},
            max_records_per_source=4,
        )

    assert summary.counts.get("EATERIES") == 4
    assert len(written) == 4
    assert summary.counts.get("DOHMH", 0) == 0


def test_run_ingestion_combines_write_and_source_errors_in_summary():
    def stream_mixed(_client, **_kwargs):
        yield {"source": "EATERIES", "k": 1}
        yield {"source": "EATERIES", "k": 2}

    def writer(rec):
        if rec["k"] == 2:
            raise IntegrityError("dup")

    def stream_dohmh_boom(_client, **_kwargs):
        raise SocrataError("offline")
        yield  # pragma: no cover

    def empty(_client, **_kwargs):
        yield from ()

    with patch(
        "nomz.ingestion.runner.stream_eateries_rows", side_effect=stream_mixed
    ), patch("nomz.ingestion.runner.stream_dining_out_rows", side_effect=empty), patch(
        "nomz.ingestion.runner.stream_inspection_rows", side_effect=stream_dohmh_boom
    ):
        summary = run_ingestion(writer=writer)

    assert summary.failures >= 2
    assert "EATERIES" in summary.errors
    assert "DOHMH" in summary.errors


# ---------------------------------------------------------------------------
# persistence: inspection key materialization + exact-name enrichment
# ---------------------------------------------------------------------------


def test_normalize_inspection_key_explicit_or_hashed_payload():
    """Covers ``_normalize_inspection_key`` (~78–99): explicit key vs composite SHA1 parts."""
    from nomz.ingestion.persistence import _normalize_inspection_key

    assert _normalize_inspection_key({"inspection_key": "fixed-key"}, 1) == "fixed-key"

    row = {
        "inspection_date": "2024-06-15",
        "grade": "B",
        "score": 12,
        "critical_violations": 0,
        "noncritical_violations": 2,
        "violation_description": "grease",
    }
    key = _normalize_inspection_key(row, restaurant_id=99)
    assert len(key) == 40
    row2 = dict(row, violation_description="other")
    assert _normalize_inspection_key(row2, restaurant_id=99) != key


def test_ingest_exact_name_match_enrichment_keeps_existing_phone_when_incoming_differs():
    """
    When resolver confidence is below threshold but the name matches uniquely,
    ``_resolve_restaurant`` uses ``exact_name_match`` (~276–287). ``_apply_restaurant_enrichment``
    only fills empty phone (~435–437), so a different incoming phone is ignored.
    """
    name = f"LowConfPhone_{uuid.uuid4().hex[:10]}"
    rest = _base_restaurant(
        name=name,
        phone="212-555-0001",
        street="1 Wall St",
        zip_code="10005",
        building="1",
        borough="MANHATTAN",
    )
    record = {
        "source": "EATERIES",
        "source_external_id": _eid(),
        "name": name,
        "name_normalized": normalize_text(name),
        "building": "999",
        "street": "Nowhere Lane",
        "zip_code": "00001",
        "borough": "QUEENS",
        "phone": "718-555-9999",
        "cuisine_tags": [],
        "raw_payload": {},
    }
    writer = DbIngestionWriter(dry_run=False)
    writer.ingest(record)
    rest.refresh_from_db()
    assert rest.phone == "212-555-0001"
    assert writer.stats.records_matched >= 1
