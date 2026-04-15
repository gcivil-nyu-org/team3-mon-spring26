from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import SimpleTestCase

from nomz.ingestion.persistence import DbIngestionWriter


class _CandidateQS:
    def __init__(self):
        self._rows = []

    def filter(self, **_kwargs):
        return self

    def exists(self):
        return False

    def __iter__(self):
        return iter(self._rows)


class PersistenceCoverageTests(SimpleTestCase):
    def test_resolve_restaurant_matched_record_updates_and_syncs(self):
        writer = DbIngestionWriter(dry_run=False)
        record = {
            "source": "EATERIES",
            "name": "Matched Spot",
            "zip_code": "10001",
            "street": "Main St",
        }
        matched_payload = {"id": "77"}
        matched_restaurant = MagicMock(id=77)

        with patch.object(
            writer, "_find_restaurant_by_source_link", return_value=None
        ), patch(
            "nomz.ingestion.persistence.Restaurant.objects.filter",
            return_value=_CandidateQS(),
        ), patch(
            "nomz.ingestion.persistence.resolve_restaurant",
            return_value=(matched_payload, 0.94, "resolver-match"),
        ), patch(
            "nomz.ingestion.persistence.Restaurant.objects.get",
            return_value=matched_restaurant,
        ) as mock_get, patch.object(
            writer, "_apply_restaurant_enrichment"
        ) as mock_enrich, patch.object(
            writer, "_sync_restaurant_search"
        ) as mock_sync:
            result = writer._resolve_restaurant(record)

        assert result is matched_restaurant
        mock_get.assert_called_once_with(id=77)
        mock_enrich.assert_called_once_with(matched_restaurant, record)
        mock_sync.assert_called_once_with(matched_restaurant)
        assert writer.stats.records_matched == 1
        assert writer.stats.records_updated == 1

    def test_upsert_source_link_existing_record_updates_fields_and_stats(self):
        writer = DbIngestionWriter(dry_run=False)
        existing = MagicMock()
        restaurant = MagicMock()
        restaurant.id = 123
        record = {
            "source": "DOHMH",
            "source_external_id": "SRC-1",
            # intentionally omit optional external fields to cover fallback defaults
            "raw_payload": {"x": 1},
            "match_confidence": 0.82,
            "street": "Broadway",
            "zip_code": "10010",
        }

        with patch(
            "nomz.ingestion.persistence.RestaurantSourceRecord.objects.filter"
        ) as mock_filter:
            mock_filter.return_value.first.return_value = existing
            writer._upsert_source_link(restaurant, record, count_stats=True)

        # Existing row should be updated/saved with the explicit update field list.
        assert existing.source == "DOHMH"
        assert existing.external_id == "SRC-1"
        assert existing.external_name == ""
        assert existing.external_address == "Broadway, 10010"
        assert existing.raw_payload == {"x": 1}
        assert existing.confidence == 0.82
        existing.save.assert_called_once()
        assert writer.stats.records_updated == 1

    def test_upsert_dining_out_profile_missing_optional_fields_and_integrity_error(self):
        writer = DbIngestionWriter(dry_run=False)
        restaurant = MagicMock()
        restaurant.id = 999

        # No metadata -> early return branch.
        with patch(
            "nomz.ingestion.persistence.DiningOutLocation.objects.update_or_create"
        ) as mock_update:
            writer._upsert_dining_out_profile(restaurant, {"source": "DINING_OUT"})
            mock_update.assert_not_called()

        # Partial metadata (missing many optional fields) -> defaults coercion path.
        partial_record = {
            "source": "DINING_OUT",
            "dining_out_metadata": {
                "license_status": "ACTIVE",
                # missing location_type -> should fallback to "unknown"
                "capacity_estimate": "",
            },
        }
        with patch(
            "nomz.ingestion.persistence.DiningOutLocation.objects.update_or_create"
        ) as mock_update:
            writer._upsert_dining_out_profile(restaurant, partial_record)
            mock_update.assert_called_once()
            kwargs = mock_update.call_args.kwargs
            assert kwargs["restaurant"] is restaurant
            defaults = kwargs["defaults"]
            assert defaults["license_type"] is None
            assert defaults["license_status"] == "ACTIVE"
            assert defaults["location_type"] == "unknown"
            assert defaults["capacity_estimate"] == 0

        # Forced DB write failure path for this block.
        with patch(
            "nomz.ingestion.persistence.DiningOutLocation.objects.update_or_create",
            side_effect=IntegrityError("forced write error"),
        ):
            try:
                writer._upsert_dining_out_profile(restaurant, partial_record)
                raised = False
            except IntegrityError:
                raised = True
            assert raised is True
