from unittest.mock import MagicMock, patch

from django.db import IntegrityError, OperationalError
from django.test import TestCase

from nomz.ingestion.persistence import (
    DbIngestionWriter,
    IngestionRunContext,
    IngestionStats,
    _normalize_source_record_id,
)
from nomz.models import Restaurant


class _CandidateQS:
    def __init__(self):
        self._rows = []

    def filter(self, **_kwargs):
        return self

    def exists(self):
        return False

    def __iter__(self):
        return iter(self._rows)


class PersistenceCoverageTests(TestCase):
    def test_normalize_source_record_id_hashes_seed_fields_without_external_id(self):
        row = {
            "name": "Near Match Pizza",
            "street": "Main St",
            "zip_code": "10001",
            "borough": "Manhattan",
            "latitude": "40.7128",
            "longitude": "-74.0060",
        }
        source_id = _normalize_source_record_id("EATERIES", row)
        assert len(source_id) == 40  # sha1 hex digest length
        assert source_id != ""

        # Presence of source_external_id should bypass hashing branch.
        row["source_external_id"] = "EXT-123"
        assert _normalize_source_record_id("EATERIES", row) == "EXT-123"

    def test_ingest_retries_on_sqlite_lock_and_then_succeeds(self):
        writer = DbIngestionWriter(dry_run=False)
        record = {"source": "EATERIES", "name": "Retry Spot"}

        with patch.object(
            writer,
            "_handle_restaurant_source_record",
            side_effect=[OperationalError("database is locked"), None],
        ) as mock_handle, patch("nomz.ingestion.persistence.time.sleep") as mock_sleep:
            writer.ingest(record)

        assert mock_handle.call_count == 2
        assert mock_sleep.called
        assert writer.stats.records_failed == 0
        assert writer.stats.records_processed == 1

    def test_ingest_raises_and_counts_failure_for_non_lock_operational_error(self):
        writer = DbIngestionWriter(dry_run=False)
        record = {"source": "EATERIES", "name": "Fail Spot"}

        with patch.object(
            writer,
            "_handle_restaurant_source_record",
            side_effect=OperationalError("some other db error"),
        ):
            try:
                writer.ingest(record)
                raised = False
            except OperationalError:
                raised = True
        assert raised is True
        assert writer.stats.records_failed == 1

    def test_coerce_date_parsing_branches(self):
        writer = DbIngestionWriter(dry_run=True)

        # ISO parse branch (fromisoformat)
        assert str(writer._coerce_date("2026-04-15T11:30:00")) == "2026-04-15"
        # "T" split fallback branch
        assert str(writer._coerce_date("2026-04-16Tbad")) == "2026-04-16"
        # fmt loop branch
        assert str(writer._coerce_date("04/17/2026")) == "2026-04-17"
        # final none branch
        assert writer._coerce_date("not-a-date") is None

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

    def test_resolve_restaurant_fuzzy_like_match_with_similar_names_and_same_zip(self):
        """
        Creates two near-matching restaurants with identical ZIP and verifies
        resolver-driven match path updates existing restaurant instead of creating.
        """
        # Use real DB objects here to approximate fuzzy-match candidate setup.
        r1 = Restaurant.objects.create(
            name="Noodle House Manhattan",
            cuisine_type="other",
            price_range="$$",
            zip_code="10001",
            street="100 Main St",
            is_active=True,
        )
        Restaurant.objects.create(
            name="Noodle House Manhatan",  # intentional near-match typo
            cuisine_type="other",
            price_range="$$",
            zip_code="10001",
            street="102 Main St",
            is_active=True,
        )

        writer = DbIngestionWriter(dry_run=False)
        record = {
            "source": "EATERIES",
            "name": "Noodle House Manhattan NYC",
            "zip_code": "10001",
            "street": "100 Main St",
            "borough": "Manhattan",
        }
        with patch.object(
            writer, "_find_restaurant_by_source_link", return_value=None
        ), patch(
            "nomz.ingestion.persistence.resolve_restaurant",
            return_value=({"id": str(r1.id)}, 0.91, "fuzzy_name_zip"),
        ), patch.object(
            writer, "_apply_restaurant_enrichment"
        ) as enrich, patch.object(
            writer, "_sync_restaurant_search"
        ) as sync:
            got = writer._resolve_restaurant(record)

        assert got.id == r1.id
        enrich.assert_called_once()
        sync.assert_called_once()

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

    def test_upsert_dining_out_profile_missing_optional_fields_and_integrity_error(
        self,
    ):
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

    def test_coerce_violations_list_and_string_paths(self):
        writer = DbIngestionWriter(dry_run=True)
        assert writer._coerce_violations(["  a  ", "", "b"]) == ["a", "b"]
        assert writer._coerce_violations("  single violation  ") == ["single violation"]
        assert writer._coerce_violations("   ") == []


class IngestionRunContextCoverageTests(TestCase):
    def test_partial_success_summary_and_batch_close_error_logging(self):
        stats = IngestionStats(
            records_processed=6,
            records_created=3,
            records_updated=1,
            records_matched=1,
            records_skipped=0,
            records_failed=2,
        )

        ctx = IngestionRunContext(dataset="coverage-partial-success")

        with patch("nomz.ingestion.persistence.logger") as mock_logger:
            # Force summary save failure (lines 620-633 logging path).
            with patch.object(
                ctx.run, "save", side_effect=Exception("summary save failed")
            ):
                ctx.set_summary(
                    stats,
                    errors={"DINING_OUT": "write error", "DOHMH": "timeout"},
                    status="failed",
                )

            # In-memory fields still reflect partial-success style payload.
            assert ctx.run.records_processed == 6
            assert ctx.run.records_created == 3
            assert ctx.run.records_updated == 1
            assert ctx.run.error_count == 2
            assert ctx.run.error_log == [
                "DINING_OUT: write error",
                "DOHMH: timeout",
            ]

            # Force close-phase failure (lines 606-633 batch close logging path).
            with patch.object(
                ctx.run, "save", side_effect=Exception("batch close failed")
            ):
                result = ctx.__exit__(None, None, None)
                assert result is False

            logged_messages = [
                call.args[0] for call in mock_logger.exception.call_args_list
            ]
            assert any(
                "Failed to persist ingestion run summary" in m for m in logged_messages
            )
            assert any(
                "Failed to close ingestion run context" in m for m in logged_messages
            )
