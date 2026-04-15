import socket
import tempfile
import urllib.error
from hashlib import sha1
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from nomz.filtering import (
    apply_open_now_filter,
    apply_restaurant_filters,
    coerce_float,
    parse_bool,
    parse_multi_values,
    restaurant_ordering,
)
from nomz.ingestion.persistence import DbIngestionWriter, _normalize_inspection_key
from nomz.ingestion.sources.dining_out_feed import (
    _coerce_phone,
    _extract_coordinates,
    _parse_date,
    _parse_int,
    normalize_dining_out_row,
    stream_dining_out_rows,
)
from nomz.ingestion.sources.eateries_feed import (
    normalize_eateries_row,
    stream_eateries_rows,
)
from nomz.ingestion.sources.inspections_feed import (
    normalize_inspection_row,
    stream_inspection_rows,
)
from nomz.ingestion.sources.socrata_client import (
    SocrataClient,
    SocrataError,
    SocrataResource,
)
from nomz.ingestion.utils.normalization import normalize_text
from nomz.models import Restaurant


class _FakeInspectionClient:
    def __init__(self, rows):
        self.rows = rows

    def fetch_all(self, _resource, **_kwargs):
        for row in self.rows:
            yield row


class _FakeRowsClient:
    def __init__(self, rows):
        self.rows = rows

    def fetch_all(self, _resource, **_kwargs):
        for row in self.rows:
            yield row


class InspectionFeedNormalizationTests(SimpleTestCase):
    def test_normalize_inspection_row_maps_fields_and_flags(self):
        row = {
            "camis": "12345",
            "dba": "Sample Bistro",
            "boro": "Brooklyn",
            "building": "20",
            "street": "Main Street",
            "zipcode": "11211",
            "phone": "2125550000",
            "cuisine_description": "American",
            "inspection_date": "2025-02-01T00:00:00.000",
            "inspection_type": "Cycle Inspection / Initial Inspection",
            "action": "Violations were cited in the following area(s).",
            "critical_flag": "Critical",
            "violation_description": "Food from unapproved source.",
            "grade": "A",
            "score": "11",
            "latitude": "40.7128",
            "longitude": "-74.0060",
        }

        normalized = normalize_inspection_row(row)
        self.assertEqual(normalized["source"], "DOHMH")
        self.assertEqual(normalized["source_external_id"], "12345")
        self.assertEqual(normalized["building"], "20")
        self.assertEqual(normalized["critical_violations"], 1)
        self.assertEqual(normalized["noncritical_violations"], 0)
        self.assertEqual(normalized["violation_count"], 1)
        self.assertEqual(
            normalized["inspection_key"],
            "12345|2025-02-01|Cycle Inspection / Initial Inspection|Violations were cited in the following area(s).",
        )
        self.assertEqual(
            normalized["violation_description"], ["Food from unapproved source."]
        )

    def test_stream_inspection_rows_groups_same_inspection(self):
        rows = [
            {
                "camis": "77777",
                "dba": "Grouping Cafe",
                "boro": "Queens",
                "building": "10",
                "street": "Queens Blvd",
                "zipcode": "11375",
                "inspection_date": "2025-01-10T00:00:00.000",
                "inspection_type": "Cycle Inspection / Initial Inspection",
                "action": "Violations were cited in the following area(s).",
                "critical_flag": "Critical",
                "violation_description": "Critical violation A",
                "grade": "B",
                "score": "17",
            },
            {
                "camis": "77777",
                "dba": "Grouping Cafe",
                "boro": "Queens",
                "building": "10",
                "street": "Queens Blvd",
                "zipcode": "11375",
                "inspection_date": "2025-01-10T00:00:00.000",
                "inspection_type": "Cycle Inspection / Initial Inspection",
                "action": "Violations were cited in the following area(s).",
                "critical_flag": "Not Critical",
                "violation_description": "Noncritical violation B",
                "grade": "B",
                "score": "17",
            },
        ]

        records = list(stream_inspection_rows(_FakeInspectionClient(rows)))
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["critical_violations"], 1)
        self.assertEqual(record["noncritical_violations"], 1)
        self.assertEqual(record["violation_count"], 2)
        self.assertEqual(len(record["violation_description"]), 2)


class FilteringUtilityTests(SimpleTestCase):
    def test_coerce_float_and_parse_bool(self):
        self.assertEqual(coerce_float(" 12.5 "), 12.5)
        self.assertIsNone(coerce_float(""))
        self.assertIsNone(coerce_float("nope"))
        self.assertTrue(parse_bool("YES"))
        self.assertFalse(parse_bool("off"))

    def test_parse_multi_values_and_ordering(self):
        self.assertEqual(
            parse_multi_values([" vegan,halal ", "vegan", None, "kosher"]),
            ["vegan", "halal", "kosher"],
        )
        self.assertEqual(
            restaurant_ordering("grade_desc"),
            ("-grade_score_latest", "-composite_score", "name"),
        )
        self.assertEqual(restaurant_ordering("unknown"), ("-composite_score", "name"))

    def test_apply_open_now_filter(self):
        class StubRestaurant:
            def __init__(self, open_now):
                self.open_now = open_now

            def is_open_now(self):
                return self.open_now

        filtered = apply_open_now_filter(
            [StubRestaurant(True), StubRestaurant(False), StubRestaurant(True)]
        )
        self.assertEqual(len(filtered), 2)


class RestaurantFilteringQueryTests(TestCase):
    def setUp(self):
        Restaurant.objects.create(
            name="Alpha Vegan",
            cuisine="vegan",
            cuisine_type="vegan",
            cuisine_tags=["vegan", "gluten-free"],
            description="Great vegan bowls",
            borough="Queens",
            neighborhood="Astoria",
            street="Main Street",
            zip_code="11101",
            grade_score_latest=90,
            composite_score=88,
            latitude=40.70,
            longitude=-73.90,
            price_range="$",
            is_active=True,
        )
        Restaurant.objects.create(
            name="Bravo Sushi",
            cuisine="japanese",
            cuisine_type="japanese",
            cuisine_tags=["sushi"],
            description="Premium omakase",
            borough="Manhattan",
            neighborhood="Midtown",
            street="Park Ave",
            zip_code="10001",
            grade_score_latest=80,
            composite_score=95,
            latitude=40.75,
            longitude=-73.98,
            price_range="$$$",
            is_active=True,
        )
        Restaurant.objects.create(
            name="Closed Place",
            cuisine="american",
            cuisine_type="american",
            description="Should never show",
            borough="Brooklyn",
            neighborhood="Williamsburg",
            composite_score=60,
            is_active=False,
            price_range="$$",
        )

    def test_apply_restaurant_filters_search_and_range(self):
        params = {
            "search": "vegan",
            "min_score": "80",
            "max_score": "90",
            "price_range": "$",
            "min_rating": "85",
        }
        qs = apply_restaurant_filters(Restaurant.objects.all(), params=params)
        self.assertEqual(list(qs.values_list("name", flat=True)), ["Alpha Vegan"])

    def test_apply_restaurant_filters_neighborhood_cuisine_dietary(self):
        class Params(dict):
            def getlist(self, key):
                return self.get(key, [])

        params = Params(
            neighborhood="Midtown",
            cuisine="japanese",
            dietary=["sushi"],
        )
        qs = apply_restaurant_filters(
            Restaurant.objects.all(), params=params, require_coordinates=True
        )
        self.assertEqual(list(qs.values_list("name", flat=True)), ["Bravo Sushi"])

    def test_apply_restaurant_filters_invalid_range_returns_none(self):
        params = {"min_score": "95", "max_score": "10"}
        qs = apply_restaurant_filters(Restaurant.objects.all(), params=params)
        self.assertEqual(qs.count(), 0)


class DiningOutFeedTests(SimpleTestCase):
    def test_helpers_parse_and_extract(self):
        self.assertEqual(_coerce_phone("212-555 1212"), "2125551212")
        self.assertIsNone(_parse_date("2025-01-02"))
        self.assertIsNone(_parse_date("bad-date"))
        self.assertEqual(_parse_int("12.9"), 12)
        self.assertIsNone(_parse_int("oops"))

        lat, lon = _extract_coordinates({"location": "POINT (-73.991 40.733)"})
        self.assertEqual((lat, lon), ("40.733000", "-73.991000"))

    def test_normalize_and_stream_dining_out_rows(self):
        row = {
            "id": "d1",
            "business_legal_name": "Dining Out Spot",
            "street": "Broadway",
            "building_number": "123",
            "postcode": "10010",
            "borough": "Manhattan",
            "phone": "212-555-4444",
            "website": "https://example.com",
            "location": {"latitude": "40.7128", "longitude": "-74.0060"},
            "cuisine": "Italian, Pizza",
            "license_issue_date": "2025-03-01",
            "license_expiration_date": "2026-03-01",
            "seats": "42",
        }
        normalized = normalize_dining_out_row(row)
        self.assertEqual(normalized["name"], "Dining Out Spot")
        self.assertEqual(normalized["cuisine_tags"], ["ITALIAN", "PIZZA"])
        self.assertEqual(normalized["dining_out_metadata"]["capacity_estimate"], 42)

        records = list(stream_dining_out_rows(_FakeRowsClient([row, {"id": "x"}])))
        self.assertEqual(len(records), 1)


class EateriesFeedTests(SimpleTestCase):
    def test_normalize_and_stream_eateries_rows(self):
        row = {
            "camis": "1",
            "dba": "Eateries Place",
            "street": "5th Ave",
            "building": "10",
            "zipcode": "10011",
            "boro": "Manhattan",
            "phone": "2125557777",
            "latitude": "40.7400",
            "longitude": "-73.9900",
            "cuisine_description": "Thai, Vegan",
        }
        normalized = normalize_eateries_row(row)
        self.assertEqual(normalized["name_normalized"], "EATERIES PLACE")
        self.assertEqual(normalized["cuisine_tags"], ["THAI", "VEGAN"])

        records = list(stream_eateries_rows(_FakeRowsClient([row, {"camis": "2"}])))
        self.assertEqual(len(records), 1)


class _FakeHTTPResponse:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class SocrataClientTests(SimpleTestCase):
    def test_fetch_page_success_and_api_error_shape(self):
        client = SocrataClient(max_retries=0)
        resource = SocrataResource(dataset_id="abc", name="Resource")

        with patch(
            "urllib.request.urlopen", return_value=_FakeHTTPResponse('[{"id": 1}]')
        ):
            page = client.fetch_page(resource, where=None, limit=10, offset=0)
        self.assertEqual(page, [{"id": 1}])

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse('{"error": true, "message": "bad"}'),
        ):
            with self.assertRaises(SocrataError):
                client.fetch_page(resource, where=None, limit=10, offset=0)

    def test_fetch_page_retries_timeout_then_success(self):
        client = SocrataClient(max_retries=1, retry_backoff_seconds=0)
        resource = SocrataResource(dataset_id="abc", name="RetryResource")
        calls = [
            urllib.error.URLError(socket.timeout("timed out")),
            _FakeHTTPResponse("[]"),
        ]

        def fake_urlopen(*_args, **_kwargs):
            result = calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch(
            "time.sleep", return_value=None
        ):
            page = client.fetch_page(resource, where=None, limit=10, offset=0)
        self.assertEqual(page, [])

    def test_fetch_all_paginates(self):
        client = SocrataClient(max_retries=0)
        resource = SocrataResource(dataset_id="abc", name="Paged")
        with patch.object(
            client,
            "fetch_page",
            side_effect=[[{"id": 1}, {"id": 2}], [{"id": 3}], []],
        ):
            rows = list(client.fetch_all(resource, limit=2))
        self.assertEqual(rows, [{"id": 1}, {"id": 2}, {"id": 3}])


class IngestionPersistenceTests(TestCase):
    def test_existing_name_is_reused_when_name_is_already_taken(self):
        existing = Restaurant.objects.create(
            name="Duplicate Name Bistro",
            display_name="Duplicate Name Bistro",
            name_normalized="duplicate name bistro",
            borough="MANHATTAN",
            zip_code="10001",
        )

        writer = DbIngestionWriter(dry_run=False)
        record = {
            "source": "DOHMH",
            "source_external_id": "12345678",
            "name": "Duplicate Name Bistro",
            "name_normalized": "duplicate name bistro",
            "building": "10",
            "street": "W 31 ST",
            "borough": "MANHATTAN",
            "zip_code": "10001",
            "inspection_date": "2025-01-01",
            "inspection_type": "Cycle Inspection / Initial Inspection",
            "action": "No violations were recorded at the time of this inspection.",
            "critical_violations": 0,
            "noncritical_violations": 0,
            "violation_count": 0,
            "violation_description": [],
            "inspection_key": "12345678|2025-01-01|Cycle Inspection / Initial Inspection|No violations were recorded at the time of this inspection.",
            "raw_payload": {},
        }

        writer.ingest(record)

        self.assertEqual(writer.stats.records_failed, 0)
        self.assertEqual(
            Restaurant.objects.filter(name="Duplicate Name Bistro").count(), 1
        )
        self.assertTrue(
            Restaurant.objects.filter(id=existing.id, street="W 31 ST").exists()
        )


class InspectionKeyNormalizationUnitTests(SimpleTestCase):
    def test_normalize_inspection_key_uses_inspection_key_when_present(self):
        row = {"inspection_key": "explicit-key"}
        self.assertEqual(_normalize_inspection_key(row, restaurant_id=123), "explicit-key")

    def test_normalize_inspection_key_hashes_fallback_fields(self):
        row = {
            "inspection_date": "2026-01-02",
            "grade": "a",
            "score": 10,
            "critical_violations": None,
            "noncritical_violations": 2,
            "violation_description": "Some issue",
        }
        got = _normalize_inspection_key(row, restaurant_id=42)
        parts = [
            "42",
            "2026-01-02",
            "a",
            "10",
            "",
            "2",
            "Some issue",
        ]
        expected = sha1("|".join(parts).encode("utf-8")).hexdigest()
        self.assertEqual(got, expected)

        # Fallback to `violation` when `violation_description` missing.
        row2 = dict(row)
        row2.pop("violation_description")
        row2["violation"] = "Alt desc"
        got2 = _normalize_inspection_key(row2, restaurant_id=42)
        self.assertNotEqual(got2, got)


class PersistenceResolveRestaurantGapUnitTests(SimpleTestCase):
    class _QS:
        def __init__(self, *, exists_value=False, first_value=None, rows=None):
            self._exists_value = exists_value
            self._first_value = first_value
            self._rows = rows or []

        def filter(self, **_kwargs):
            return self

        def exists(self):
            return self._exists_value

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return self._first_value

        def __iter__(self):
            return iter(self._rows)

    def test_resolve_restaurant_dry_run_returns_unsaved_restaurant_and_counts_create(self):
        writer = DbIngestionWriter(dry_run=True)
        record = {
            "source": "EATERIES",
            "name": "Dry Run Spot",
            "street": "Some St",
            "zip_code": "10001",
            "borough": "Manhattan",
            "latitude": "40.7",
            "longitude": "-74.0",
        }

        with patch.object(
            writer, "_find_restaurant_by_source_link", return_value=None
        ), patch(
            "nomz.ingestion.persistence.resolve_restaurant", return_value=(None, 0.2, "none")
        ), patch(
            "nomz.ingestion.persistence.Restaurant.objects.filter",
            return_value=self._QS(exists_value=False, rows=[]),
        ):
            restaurant = writer._resolve_restaurant(record)

        self.assertIsNotNone(restaurant)
        self.assertEqual(writer.stats.records_created, 1)
        self.assertEqual(getattr(restaurant, "name", None), "Dry Run Spot")
        self.assertEqual(getattr(restaurant, "name_normalized", None), normalize_text("Dry Run Spot"))

    def test_resolve_restaurant_integrity_error_recovers_existing_and_enriches(self):
        """
        Exercises the race-condition branch (289–324): create() raises IntegrityError,
        then we re-fetch by name and enrich/sync that existing row.
        """
        writer = DbIngestionWriter(dry_run=False)
        record = {
            "source": "EATERIES",
            "name": "Race Condition Cafe",
            "street": "X",
            "zip_code": "10001",
            "borough": "Manhattan",
        }

        existing_restaurant = object()

        qs_active = self._QS(exists_value=False, rows=[])
        qs_name_none = self._QS(first_value=None)
        qs_name_existing = self._QS(first_value=existing_restaurant)

        def filter_side_effect(**kwargs):
            # Candidate searches
            if kwargs.get("is_active") is True:
                return qs_active
            # exact_name_match and IntegrityError recovery lookups
            if "name__iexact" in kwargs:
                if not hasattr(filter_side_effect, "calls"):
                    filter_side_effect.calls = 0
                filter_side_effect.calls += 1
                return qs_name_none if filter_side_effect.calls == 1 else qs_name_existing
            return self._QS()

        with patch.object(
            writer, "_find_restaurant_by_source_link", return_value=None
        ), patch(
            "nomz.ingestion.persistence.resolve_restaurant", return_value=(None, 0.0, "none")
        ), patch(
            "nomz.ingestion.persistence.Restaurant.objects.filter",
            side_effect=filter_side_effect,
        ), patch(
            "nomz.ingestion.persistence.Restaurant.objects.create",
            side_effect=IntegrityError("unique constraint"),
        ), patch.object(
            writer, "_apply_restaurant_enrichment"
        ) as enrich, patch.object(
            writer, "_sync_restaurant_search"
        ) as sync:
            got = writer._resolve_restaurant(record)

        self.assertIs(got, existing_restaurant)
        enrich.assert_called_once()
        sync.assert_called_once()
        self.assertEqual(writer.stats.records_matched, 1)
        self.assertEqual(writer.stats.records_updated, 1)


class FetchNycSourcesCommandTests(SimpleTestCase):
    def test_call_command_executes_and_reports_output(self):
        captured_kwargs = {}

        def fake_run_ingestion(**kwargs):
            captured_kwargs.update(kwargs)
            kwargs["writer"]({"source": "EATERIES", "name": "Alpha"})
            kwargs["writer"]({"source": "DOHMH", "name": "Beta"})
            return SimpleNamespace(
                total=2,
                failures=1,
                counts={"EATERIES": 1, "DINING_OUT": 0, "DOHMH": 1},
                errors={"EATERIES": "non-tabular endpoint response"},
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = f"{tmpdir}/normalized.jsonl"
            stdout = StringIO()

            with patch(
                "nomz.management.commands.fetch_nyc_sources.run_ingestion",
                side_effect=fake_run_ingestion,
            ):
                call_command(
                    "fetch_nyc_sources",
                    "--no-db",
                    "--dry-run",
                    "--pretty",
                    "--output",
                    output_path,
                    stdout=stdout,
                )

            out = stdout.getvalue()
            self.assertIn(f"Saved records to {output_path}", out)
            self.assertIn("Ingestion finished | total=2 failures=1", out)
            self.assertIn("Source errors:", out)
            self.assertIn("Tip: skip this source for now with --skip-source EATERIES.", out)
            self.assertIn("Dry-run mode: no database writes were committed.", out)
            self.assertIn('"name": "Alpha"', out)
            self.assertIn('"name": "Beta"', out)

            self.assertEqual(captured_kwargs.get("skip_sources"), set())
            self.assertEqual(captured_kwargs.get("max_records_per_source"), None)
            with open(output_path, encoding="utf-8") as fh:
                lines = [line.strip() for line in fh if line.strip()]
            self.assertEqual(len(lines), 2)
            self.assertTrue(any('"name": "Alpha"' in line for line in lines))
            self.assertTrue(any('"name": "Beta"' in line for line in lines))
