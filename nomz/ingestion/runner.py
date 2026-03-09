from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from nomz.ingestion.sources.eateries_feed import stream_eateries_rows
from nomz.ingestion.sources.dining_out_feed import stream_dining_out_rows
from nomz.ingestion.sources.inspections_feed import stream_inspection_rows
from nomz.ingestion.sources.socrata_client import SocrataClient, SocrataError


RecordWriter = Callable[[Dict], None]


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
) -> IngestionSummary:
    writer = writer or (lambda _record: None)
    skip_sources = skip_sources or set()
    client = SocrataClient(domain=domain, app_token=app_token)

    counts: Dict[str, int] = defaultdict(int)
    failure_breakdown = defaultdict(int)
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
                try:
                    writer(record)
                    counts[source_name] += 1
                except Exception as exc:
                    failures += 1
                    failure_breakdown[source_name] += 1
                    errors[source_name] = f"write_error: {exc}"
        except SocrataError as exc:
            failures += 1
            failure_breakdown[source_name] += 1
            errors[source_name] = str(exc)
        except Exception as exc:
            failures += 1
            failure_breakdown[source_name] += 1
            errors[source_name] = str(exc)

    total = sum(counts.values())
    if failure_breakdown:
        errors = {
            source_name: f"{message} ({failure_breakdown[source_name]} fail)"
            for source_name, message in errors.items()
        }

    return IngestionSummary(counts=dict(counts), total=total, failures=failures, errors=errors)
