from unittest.mock import patch

from django.test import SimpleTestCase

from nomz.ingestion.runner import run_ingestion


class RunnerCoverageTests(SimpleTestCase):
    def test_run_ingestion_continues_when_one_source_raises_exception(self):
        written = []

        def writer(record):
            written.append(record["source"])

        with patch("nomz.ingestion.runner.SocrataClient"), patch(
            "nomz.ingestion.runner.stream_eateries_rows",
            return_value=[
                {"source": "EATERIES", "id": 1},
                {"source": "EATERIES", "id": 2},
            ],
        ), patch(
            "nomz.ingestion.runner.stream_dining_out_rows",
            side_effect=Exception("simulated source failure"),
        ), patch(
            "nomz.ingestion.runner.stream_inspection_rows",
            return_value=[{"source": "DOHMH", "id": 3}],
        ):
            summary = run_ingestion(writer=writer)

        assert written == ["EATERIES", "EATERIES", "DOHMH"]
        assert summary.counts["EATERIES"] == 2
        assert summary.counts["DOHMH"] == 1
        assert "DINING_OUT" not in summary.counts
        assert summary.total == 3
        assert summary.failures == 1
        assert "DINING_OUT" in summary.errors
        assert "simulated source failure" in summary.errors["DINING_OUT"]

    def test_run_ingestion_logs_start_and_end(self):
        with patch("nomz.ingestion.runner.SocrataClient"), patch(
            "nomz.ingestion.runner.stream_eateries_rows",
            return_value=[],
        ), patch(
            "nomz.ingestion.runner.stream_dining_out_rows",
            return_value=[],
        ), patch(
            "nomz.ingestion.runner.stream_inspection_rows",
            return_value=[],
        ), patch("nomz.ingestion.runner.logger") as mock_logger:
            summary = run_ingestion(skip_sources={"DINING_OUT"}, max_records_per_source=1)

        assert summary.total == 0
        assert summary.failures == 0
        assert mock_logger.info.call_count >= 2
        first_msg = mock_logger.info.call_args_list[0][0][0]
        last_msg = mock_logger.info.call_args_list[-1][0][0]
        assert "Starting ingestion run" in first_msg
        assert "Finished ingestion run" in last_msg
