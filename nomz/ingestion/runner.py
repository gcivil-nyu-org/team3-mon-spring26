from __future__ import annotations

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import Callable, Dict, Optional

from nomz.ingestion.sources.eateries_feed import stream_eateries_rows
from nomz.ingestion.sources.dining_out_feed import stream_dining_out_rows
from nomz.ingestion.sources.inspections_feed import stream_inspection_rows
from nomz.ingestion.sources.socrata_client import SocrataClient, SocrataError

RecordWriter = Callable[[Dict], None]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionSummary:
    counts: Dict[str, int]
    total: int
    failures: int
    errors: Dict[str, str]

    @property
    def ok(self) -> bool:
        return self.failures == 0


def run_ingestion(
    app_token: Optional[str] = None,
    domain: str = "data.cityofnewyork.us",
    writer: Optional[RecordWriter] = None,
    skip_sources: Optional[set[str]] = None,
    max_records_per_source: Optional[int] = None,
) -> IngestionSummary:
    logger.info(
        "Starting ingestion run (domain=%s, skip_sources=%s, max_records_per_source=%s)",
        domain,
        sorted(skip_sources) if skip_sources else [],
        max_records_per_source,
    )
    writer = writer or (lambda _record: None)
    skip_sources = skip_sources or set()
    client = SocrataClient(domain=domain, app_token=app_token)

    counts: Dict[str, int] = defaultdict(int)
    failure_breakdown = defaultdict(int)
    write_failures: Dict[str, Counter[str]] = defaultdict(Counter)
    failures = 0
    errors: Dict[str, str] = {}

    sources = {
        "EATERIES": lambda: stream_eateries_rows(client),
        "DINING_OUT": lambda: stream_dining_out_rows(client),
        "DOHMH": lambda: stream_inspection_rows(client),
    }

    for source_name, stream_factory in sources.items():
        if source_name in skip_sources:
            continue
        try:
            for record in stream_factory():
                if (
                    max_records_per_source is not None
                    and counts[source_name] >= max_records_per_source
                ):
                    break
                try:
                    writer(record)
                    counts[source_name] += 1
                except Exception as exc:
                    failures += 1
                    failure_breakdown[source_name] += 1
                    err_text = f"{type(exc).__name__}: {exc}"
                    write_failures[source_name][err_text] += 1
                    errors[source_name] = f"write_error: {err_text}"
        except SocrataError as exc:
            failures += 1
            failure_breakdown[source_name] += 1
            existing = errors.get(source_name)
            source_error = str(exc)
            if existing:
                errors[source_name] = f"{existing}; source_error: {source_error}"
            else:
                errors[source_name] = source_error
        except Exception as exc:
            failures += 1
            failure_breakdown[source_name] += 1
            existing = errors.get(source_name)
            source_error = str(exc)
            if existing:
                errors[source_name] = f"{existing}; source_error: {source_error}"
            else:
                errors[source_name] = source_error

    total = sum(counts.values())
    if failure_breakdown:
        for source_name, counter in write_failures.items():
            top_write_errors = ", ".join(
                f"{count}x {message}" for message, count in counter.most_common(3)
            )
            if not top_write_errors:
                continue
            existing = errors.get(source_name)
            if existing:
                errors[source_name] = (
                    f"{existing}; top_write_errors: [{top_write_errors}]"
                )
            else:
                errors[source_name] = f"top_write_errors: [{top_write_errors}]"

        errors = {
            source_name: f"{message} ({failure_breakdown[source_name]} fail)"
            for source_name, message in errors.items()
        }

    summary = IngestionSummary(
        counts=dict(counts), total=total, failures=failures, errors=errors
    )
    logger.info(
        "Finished ingestion run (total=%s, failures=%s, counts=%s)",
        summary.total,
        summary.failures,
        summary.counts,
    )
    return summary
