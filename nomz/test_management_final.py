"""
Management command smoke tests: `call_command` with mocks for network / heavy work.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from nomz.ingestion.runner import IngestionSummary
from nomz.models import (
    RecalculatedRecommendation,
    RecommendationModelMetric,
    Restaurant,
    UserInteractionHistory,
    UserPreference,
)

pytestmark = pytest.mark.django_db


def _uid() -> str:
    return uuid.uuid4().hex[:10]


def _summary(**overrides):
    base = dict(
        counts={"EATERIES": 1, "DINING_OUT": 1, "DOHMH": 1},
        total=3,
        failures=0,
        errors={},
    )
    base.update(overrides)
    return IngestionSummary(**base)


# --- cleanup_restaurant_data -------------------------------------------------


def test_cleanup_restaurant_data_dry_run():
    out = StringIO()
    call_command("cleanup_restaurant_data", stdout=out)
    text = out.getvalue()
    assert "Candidates to deactivate" in text
    assert "Dry run" in text


def test_cleanup_restaurant_data_apply_deactivates_orphan():
    Restaurant.objects.create(
        owner=None,
        name=f"OrphanCmd_{_uid()}",
        cuisine_type="italian",
        price_range="$$",
        is_active=True,
        latitude=None,
        longitude=None,
    )
    out = StringIO()
    call_command("cleanup_restaurant_data", "--apply", stdout=out)
    assert "Deactivated" in out.getvalue()
    assert (
        Restaurant.objects.filter(name__startswith="OrphanCmd_")
        .filter(is_active=False)
        .exists()
    )


# --- fetch_nyc_sources -------------------------------------------------------


@patch("nomz.management.commands.fetch_nyc_sources.run_ingestion")
def test_fetch_nyc_sources_no_db(mock_run):
    captured = {}

    def _run(**kwargs):
        writer = kwargs.get("writer")
        if writer:
            writer({"source": "EATERIES", "id": "1"})
        captured["kwargs"] = kwargs
        return _summary()

    mock_run.side_effect = _run
    out = StringIO()
    call_command(
        "fetch_nyc_sources",
        "--no-db",
        max_records_per_source=2,
        stdout=out,
    )
    mock_run.assert_called_once()
    assert captured["kwargs"]["max_records_per_source"] == 2
    assert "Ingestion finished" in out.getvalue()


@patch("nomz.management.commands.fetch_nyc_sources.run_ingestion")
def test_fetch_nyc_sources_dry_run_writes_db_stats(mock_run):
    mock_run.return_value = _summary(failures=0)
    out = StringIO()
    call_command(
        "fetch_nyc_sources",
        "--dry-run",
        max_records_per_source=1,
        stdout=out,
    )
    assert "DB write stats" in out.getvalue()
    assert "Dry-run mode" in out.getvalue()


@patch("nomz.management.commands.fetch_nyc_sources.run_ingestion")
def test_fetch_nyc_sources_jsonl_output(mock_run, tmp_path):
    def _side_effect(**kwargs):
        writer = kwargs.get("writer")
        if writer:
            writer({"source": "DOHMH", "k": 1})
        return _summary(counts={"DOHMH": 1}, total=1)

    mock_run.side_effect = _side_effect
    out_path = tmp_path / "out.jsonl"
    out = StringIO()
    call_command(
        "fetch_nyc_sources",
        "--no-db",
        output=str(out_path),
        stdout=out,
    )
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8").strip()
    assert "Saved records" in out.getvalue()


@patch("nomz.management.commands.fetch_nyc_sources.run_ingestion")
def test_fetch_nyc_sources_shows_errors_and_tip(mock_run):
    mock_run.return_value = _summary(
        counts={"EATERIES": 0, "DINING_OUT": 0, "DOHMH": 0},
        total=0,
        failures=1,
        errors={"EATERIES": "Upstream returned non-tabular payload"},
    )
    out = StringIO()
    call_command("fetch_nyc_sources", "--no-db", stdout=out)
    assert "Source errors" in out.getvalue()
    assert "skip-source" in out.getvalue().lower() or "EATERIES" in out.getvalue()


# --- recalculate_recommendations ---------------------------------------------


@patch(
    "nomz.management.commands.recalculate_recommendations.recalculate_user_recommendation_model"
)
def test_recalculate_recommendations_single_user(mock_recalc, db):
    u = User.objects.create_user(
        username=f"rec_u_{_uid()}",
        email=f"{_uid()}@r.com",
        password="Str0ngPass!x",
    )
    prefs = UserPreference.objects.create(
        user=u,
        minimum_interactions_for_learning=1,
    )
    r = Restaurant.objects.create(
        owner=None,
        name=f"RecRest_{_uid()}",
        cuisine_type="thai",
        price_range="$",
        is_active=True,
    )
    UserInteractionHistory.objects.create(
        user=u,
        restaurant=r,
        interaction_type="view",
    )
    assert prefs.has_enough_data_for_learning()

    out = StringIO()
    call_command(
        "recalculate_recommendations",
        user_id=u.id,
        min_interactions=1,
        stdout=out,
    )
    mock_recalc.assert_called_once_with(u.id)
    assert "Successfully recalculated" in out.getvalue()


@patch(
    "nomz.management.commands.recalculate_recommendations.recalculate_user_recommendation_model"
)
def test_recalculate_recommendations_all_users_skips_without_data(mock_recalc, db):
    u = User.objects.create_user(
        username=f"rec_n_{_uid()}",
        email=f"{_uid()}@n.com",
        password="Str0ngPass!x",
    )
    UserPreference.objects.create(user=u, minimum_interactions_for_learning=99)
    out = StringIO()
    call_command("recalculate_recommendations", stdout=out)
    mock_recalc.assert_not_called()


@patch(
    "nomz.management.commands.recalculate_recommendations.recalculate_user_recommendation_model"
)
def test_recalculate_recommendations_daily_metrics(mock_recalc, db):
    u = User.objects.create_user(
        username=f"rec_m_{_uid()}",
        email=f"{_uid()}@m.com",
        password="Str0ngPass!x",
    )
    prefs = UserPreference.objects.create(
        user=u,
        minimum_interactions_for_learning=1,
    )
    rest = Restaurant.objects.create(
        owner=None,
        name=f"RecMet_{_uid()}",
        cuisine_type="italian",
        price_range="$$",
        is_active=True,
    )
    UserInteractionHistory.objects.create(
        user=u,
        restaurant=rest,
        interaction_type="recommendation_clicked",
    )
    RecalculatedRecommendation.objects.create(
        user=u,
        restaurant=rest,
        recommendation_score=Decimal("80.00"),
        user_interacted=True,
        days_to_interaction=2,
    )
    # Ensure calculated_at matches today for the metrics command
    import datetime

    today_utc = timezone.now().astimezone(datetime.timezone.utc).date()
    noon_utc = timezone.make_aware(
        datetime.datetime.combine(today_utc, datetime.time(12, 0)),
        timezone=datetime.timezone.utc,
    )
    RecalculatedRecommendation.objects.all().update(calculated_at=noon_utc)
    assert prefs.has_enough_data_for_learning()

    out = StringIO()
    call_command("recalculate_recommendations", user_id=u.id, stdout=out)
    mock_recalc.assert_called_once()
    # We check if the command output contains at least a success message
    assert "Successfully recalculated" in out.getvalue()

    assert RecommendationModelMetric.objects.exists()
    metric = RecommendationModelMetric.objects.first()
    metric.refresh_from_db()
    assert RecalculatedRecommendation.objects.get().user_id == u.id


# --- seed_synthetic_reviews ----------------------------------------------------


@patch("nomz.management.commands.seed_synthetic_reviews.refresh_restaurant_composite")
def test_seed_synthetic_reviews_dry_run(mock_refresh):
    Restaurant.objects.create(
        owner=None,
        name=f"SeedDry_{_uid()}",
        cuisine_type="mexican",
        price_range="$",
        is_active=True,
    )
    out = StringIO()
    call_command("seed_synthetic_reviews", stdout=out)
    assert "Dry run" in out.getvalue()
    mock_refresh.assert_not_called()


@patch("nomz.management.commands.seed_synthetic_reviews.refresh_restaurant_composite")
def test_seed_synthetic_reviews_apply_minimal(mock_refresh, db):
    Restaurant.objects.create(
        owner=None,
        name=f"SeedApply_{_uid()}",
        cuisine_type="american",
        price_range="$$",
        is_active=True,
        borough="Manhattan",
    )
    out = StringIO()
    call_command(
        "seed_synthetic_reviews",
        "--apply",
        "--reviewer-pool-size",
        "5",
        "--min-reviews",
        "1",
        "--max-reviews",
        "1",
        stdout=out,
    )
    assert "seeded successfully" in out.getvalue().lower()
    mock_refresh.assert_called()
    from nomz.models import Review

    assert Review.objects.filter(restaurant__name__startswith="SeedApply_").exists()


def test_seed_synthetic_reviews_apply_no_targets_still_ok(db):
    """`--apply` completes even when the candidate queryset is empty."""
    out = StringIO()
    call_command(
        "seed_synthetic_reviews",
        "--apply",
        "--reviewer-pool-size",
        "5",
        "--min-reviews",
        "1",
        "--max-reviews",
        "1",
        stdout=out,
    )
    assert "Synthetic reviews seeded successfully" in out.getvalue()
