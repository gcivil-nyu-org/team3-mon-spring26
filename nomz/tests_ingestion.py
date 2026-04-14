import socket
import urllib.error
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from nomz.filtering import (
    apply_open_now_filter,
    apply_restaurant_filters,
    coerce_float,
    parse_bool,
    parse_multi_values,
    restaurant_ordering,
)
from nomz.ingestion.persistence import DbIngestionWriter
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
