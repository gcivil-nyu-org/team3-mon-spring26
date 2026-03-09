import json
import os
from collections import deque
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from nomz.ingestion.persistence import DbIngestionWriter, IngestionRunContext
from nomz.ingestion.runner import run_ingestion


class Command(BaseCommand):
    help = "Fetch and normalize NYC datasets from Socrata endpoints."

    def add_arguments(self, parser):
        parser.add_argument("--app-token", default=None, help="Optional Socrata app token")
        parser.add_argument(
            "--skip-source",
            action="append",
            default=[],
            choices=["EATERIES", "DINING_OUT", "DOHMH"],
            help="Skip one or more sources",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Write normalized records to this jsonl file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the pipeline without writing to the database",
        )
        parser.add_argument(
            "--no-db",
            action="store_true",
            help="Do not write records to the database (json output only)",
        )
        parser.add_argument(
            "--pretty",
            action="store_true",
            help="Pretty print rows in command output",
        )

    def handle(self, *args, **options):
        app_token = options["app_token"] or os.getenv("SOC_DATA_APP_TOKEN")
        skip_sources = {value.upper() for value in options["skip_source"]}
        output = options["output"]
        pretty = options["pretty"]
        dry_run = options["dry_run"]
        no_db = options["no_db"]

        db_writer = None if no_db else DbIngestionWriter(dry_run=dry_run)
        writer_fns = []
        close_fns = deque()

        if output:
            output_writer, output_close = self._make_writer(output, pretty)
            writer_fns.append(output_writer)
            close_fns.append(output_close)
        if db_writer is not None:
            writer_fns.append(db_writer.ingest)

        writer = self._compose_writers(writer_fns)

        run_context = IngestionRunContext(dataset="nyc-socrata-ingest") if db_writer is not None else None

        try:
            if run_context is not None:
                with run_context:
                    summary = run_ingestion(
                        app_token=app_token,
                        domain=getattr(settings, "SOC_DATA_DOMAIN", "data.cityofnewyork.us"),
                        writer=writer,
                        skip_sources=skip_sources,
                    )
                    run_status = "failed" if summary.failures else "success"
                    run_context.set_summary(
                        db_writer.stats,
                        errors=summary.errors,
                        status=run_status,
                    )
            else:
                summary = run_ingestion(
                    app_token=app_token,
                    domain=getattr(settings, "SOC_DATA_DOMAIN", "data.cityofnewyork.us"),
                    writer=writer,
                    skip_sources=skip_sources,
                )
        finally:
            while close_fns:
                close_fns.popleft()()

        if output:
            self.stdout.write(self.style.SUCCESS(f"Saved records to {output}"))
        if db_writer is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    "DB write stats | processed=%s created=%s updated=%s "
                    "matched=%s skipped=%s failed=%s"
                    % (
                        db_writer.stats.records_processed,
                        db_writer.stats.records_created,
                        db_writer.stats.records_updated,
                        db_writer.stats.records_matched,
                        db_writer.stats.records_skipped,
                        db_writer.stats.records_failed,
                    )
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Ingestion finished | total=%s failures=%s | "
                "eateries=%s dining_out=%s inspections=%s"
                % (
                    summary.total,
                    summary.failures,
                    summary.counts.get("EATERIES", 0),
                    summary.counts.get("DINING_OUT", 0),
                    summary.counts.get("DOHMH", 0),
                )
            )
        )

        if summary.errors:
            self.stdout.write(self.style.WARNING("Source errors:"))
            for source_name, message in summary.errors.items():
                self.stdout.write(self.style.WARNING(f"- {source_name}: {message}"))
                if (
                    source_name == "EATERIES"
                    and "non-tabular" in message.lower()
                    and not skip_sources.__contains__("EATERIES")
                ):
                    self.stdout.write(
                        self.style.WARNING(
                            "Tip: skip this source for now with --skip-source EATERIES."
                        )
                    )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run mode: no database writes were committed."))

    def _compose_writers(self, writers):
        if not writers:
            return lambda _record: None
        if len(writers) == 1:
            return writers[0]

        def _writer(record):
            for writer_fn in writers:
                writer_fn(record)

        return _writer

    def _make_writer(self, output, pretty=False):
        sink = open(Path(output), "w", encoding="utf-8") if output else None

        def _writer(record):
            line = json.dumps(record, ensure_ascii=False, sort_keys=True)
            if pretty:
                self.stdout.write(line)
            if sink:
                sink.write(line + "\n")

        def _close():
            if sink:
                sink.close()

        return _writer, _close
