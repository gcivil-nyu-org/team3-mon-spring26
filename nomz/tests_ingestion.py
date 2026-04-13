from django.test import SimpleTestCase, TestCase

from nomz.ingestion.persistence import DbIngestionWriter
from nomz.ingestion.sources.inspections_feed import (
    normalize_inspection_row,
    stream_inspection_rows,
)
from nomz.models import Restaurant


class _FakeInspectionClient:
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
