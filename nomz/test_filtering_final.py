"""
Tests for `nomz.filtering` (restaurant search / filter pipeline and helpers).
"""

from __future__ import annotations

import uuid
from datetime import datetime, time
from unittest.mock import patch

import pytest
from django.http import QueryDict
from django.utils import timezone as django_timezone

from nomz.filtering import (
    DIETARY_OPTIONS,
    apply_open_now_filter,
    apply_restaurant_filters,
    coerce_float,
    parse_bool,
    parse_multi_values,
    restaurant_ordering,
)
from nomz.models import Restaurant

pytestmark = pytest.mark.django_db


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _make_restaurant(**kwargs) -> Restaurant:
    defaults = dict(
        owner=None,
        name=f"R_{_uid()}",
        description="Family friendly Italian dining room.",
        cuisine_type="italian",
        cuisine="Italian",
        cuisine_tags=["italian", "vegetarian-friendly"],
        price_range="$$",
        is_active=True,
        is_temporarily_unavailable=False,
        street="123 Main St",
        zip_code="10001",
        borough="Manhattan",
        neighborhood="SoHo",
        composite_score=75.5,
        grade_score_latest=85,
        hours_open=time(9, 0),
        hours_close=time(22, 0),
    )
    defaults.update(kwargs)
    return Restaurant.objects.create(**defaults)


@pytest.fixture
def restaurant_set(db):
    """Several restaurants with overlapping and distinct attributes."""
    nh = f"SoHoTest_{_uid()}"
    a = _make_restaurant(
        name=f"Pizza Corner {_uid()}",
        zip_code="10001",
        borough="Manhattan",
        neighborhood=nh,
        cuisine_type="italian",
        cuisine="Italian",
        composite_score=80.0,
        grade_score_latest=90,
        price_range="$$",
        latitude=40.723,
        longitude=-73.999,
    )
    b = _make_restaurant(
        name=f"Taco Stand {_uid()}",
        zip_code="11211",
        borough="Brooklyn",
        neighborhood="Williamsburg",
        cuisine_type="mexican",
        cuisine="Mexican",
        cuisine_tags=["mexican", "vegan"],
        composite_score=65.0,
        grade_score_latest=70,
        price_range="$",
        description="Quick tacos and vegan bowls.",
        latitude=40.708,
        longitude=-73.957,
    )
    c = _make_restaurant(
        name=f"Fine Dining {_uid()}",
        zip_code="10019",
        borough="Manhattan",
        neighborhood="Midtown",
        cuisine_type="french",
        cuisine="French",
        composite_score=92.0,
        grade_score_latest=95,
        price_range="$$$",
        latitude=40.761,
        longitude=-73.977,
    )
    inactive = _make_restaurant(
        name=f"Closed Place {_uid()}",
        is_active=False,
        zip_code="10002",
    )
    no_geo = _make_restaurant(
        name=f"No Lat {_uid()}",
        latitude=None,
        longitude=None,
        zip_code="10003",
    )
    return {"a": a, "b": b, "c": c, "inactive": inactive, "no_geo": no_geo, "nh": nh}


# ---------------------------------------------------------------------------
# apply_restaurant_filters
# ---------------------------------------------------------------------------


def test_apply_filters_empty_search_returns_all_active(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params=QueryDict(""))
    ids = set(out.values_list("id", flat=True))
    assert restaurant_set["inactive"].id not in ids
    assert restaurant_set["a"].id in ids
    assert restaurant_set["b"].id in ids


def test_apply_filters_whitespace_only_search_skips_text_filter(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params=QueryDict("search=   "))
    assert out.count() >= 3


def test_apply_filters_search_by_name_and_zip(restaurant_set):
    qs = Restaurant.objects.all()
    name_part = restaurant_set["a"].name.split()[0]
    by_name = apply_restaurant_filters(qs, params=QueryDict(f"search={name_part}"))
    assert restaurant_set["a"].id in set(by_name.values_list("id", flat=True))

    by_zip = apply_restaurant_filters(qs, params=QueryDict("search=11211"))
    assert restaurant_set["b"].id in set(by_zip.values_list("id", flat=True))


def test_apply_filters_search_nonexistent_zip_no_matches(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params=QueryDict("search=99999"))
    assert not out.exists()


def test_apply_filters_q_alias(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params={"q": restaurant_set["c"].name[:6]})
    assert restaurant_set["c"].id in set(out.values_list("id", flat=True))


def test_apply_filters_neighborhood_and_borough(restaurant_set):
    qs = Restaurant.objects.all()
    soho = apply_restaurant_filters(
        qs, params=QueryDict(f"neighborhood={restaurant_set['nh']}")
    )
    assert list(soho.values_list("id", flat=True)) == [restaurant_set["a"].id]

    brooklyn = apply_restaurant_filters(qs, params={"borough": "Brooklyn"})
    assert restaurant_set["b"].id in set(brooklyn.values_list("id", flat=True))


def test_apply_filters_cuisine(restaurant_set):
    qs = Restaurant.objects.all()
    mex = apply_restaurant_filters(qs, params=QueryDict("cuisine=mexican"))
    assert restaurant_set["b"].id in set(mex.values_list("id", flat=True))


def test_apply_filters_price_range_valid_and_invalid(restaurant_set):
    qs = Restaurant.objects.all()
    cheap = apply_restaurant_filters(qs, params=QueryDict("price_range=$"))
    assert set(cheap.values_list("id", flat=True)) == {restaurant_set["b"].id}

    # Invalid token → branch skipped, still returns actives
    ignore = apply_restaurant_filters(qs, params=QueryDict("price_range=INVALID"))
    assert ignore.count() >= len([restaurant_set[k] for k in ("a", "b", "c", "no_geo")])


def test_apply_filters_composite_min_max_and_aliases(restaurant_set):
    qs = Restaurant.objects.all()
    hi = apply_restaurant_filters(qs, params=QueryDict("min_composite_score=70"))
    assert restaurant_set["b"].id not in set(hi.values_list("id", flat=True))

    lo = apply_restaurant_filters(qs, params=QueryDict("max_score=70"))
    assert restaurant_set["b"].id in set(lo.values_list("id", flat=True))


def test_apply_filters_min_composite_zero_skips_min_branch(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params=QueryDict("min_composite_score=0"))
    assert out.count() >= 3


def test_apply_filters_max_composite_at_ceiling_skips_max_branch(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params=QueryDict("max_composite_score=100"))
    assert out.count() >= 3


def test_apply_filters_min_greater_than_max_returns_empty(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(
        qs,
        params=QueryDict("min_composite_score=90&max_composite_score=10"),
    )
    assert not out.exists()


def test_apply_filters_invalid_float_scores_ignored(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(
        qs,
        params=QueryDict("min_score=not-a-float&max_score=also-bad"),
    )
    assert out.count() >= 3


def test_apply_filters_min_rating(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params=QueryDict("min_rating=90"))
    assert set(out.values_list("id", flat=True)) == {
        restaurant_set["a"].id,
        restaurant_set["c"].id,
    }


def test_apply_filters_dietary_getlist(restaurant_set):
    qs = Restaurant.objects.all()
    qd = QueryDict(mutable=True)
    qd.setlist("dietary", ["vegan"])
    out = apply_restaurant_filters(qs, params=qd)
    assert restaurant_set["b"].id in set(out.values_list("id", flat=True))


def test_apply_filters_dietary_from_plain_dict_string(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params={"dietary": "  Vegan , vegan , "})
    assert restaurant_set["b"].id in set(out.values_list("id", flat=True))


def test_apply_filters_dietary_via_description(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params={"dietary": "vegetarian-friendly"})
    assert restaurant_set["a"].id in set(out.values_list("id", flat=True))


def test_apply_filters_require_coordinates(restaurant_set):
    qs = Restaurant.objects.all()
    out = apply_restaurant_filters(qs, params=QueryDict(""), require_coordinates=True)
    ids = set(out.values_list("id", flat=True))
    assert restaurant_set["no_geo"].id not in ids
    assert restaurant_set["a"].id in ids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_coerce_float_edges():
    assert coerce_float(None) is None
    assert coerce_float("") is None
    assert coerce_float("  ") is None
    assert coerce_float("12.5") == 12.5
    assert coerce_float("bad") is None


def test_parse_bool_edges():
    assert parse_bool(None) is False
    assert parse_bool("TRUE") is True
    assert parse_bool("no") is False


def test_parse_multi_values_edges():
    assert parse_multi_values(None) == []
    assert parse_multi_values(" A , a , B ") == ["a", "b"]
    assert parse_multi_values(["x", "y, z"]) == ["x", "y", "z"]
    assert parse_multi_values([None, "vegan"]) == ["vegan"]


def test_dietary_options_list_nonempty():
    assert "vegan" in DIETARY_OPTIONS


def test_restaurant_ordering_known_and_fallback():
    assert restaurant_ordering("score_desc")[0] == "-composite_score"
    assert restaurant_ordering("grade_asc")[0] == "grade_score_latest"
    assert restaurant_ordering("unknown_sort")[0] == "-composite_score"


# ---------------------------------------------------------------------------
# apply_open_now_filter
# ---------------------------------------------------------------------------


@patch("django.utils.timezone.now")
def test_apply_open_now_filter_respects_hours(mock_now, restaurant_set):
    mock_now.return_value = datetime(
        2026, 6, 15, 14, 30, 0, tzinfo=django_timezone.get_current_timezone()
    )
    open_r = restaurant_set["a"]
    closed_r = _make_restaurant(
        name=f"NightOnly {_uid()}",
        hours_open=time(22, 0),
        hours_close=time(23, 0),
        zip_code="10004",
    )
    result = apply_open_now_filter([open_r, closed_r, restaurant_set["inactive"]])
    assert open_r in result
    assert closed_r not in result
    assert restaurant_set["inactive"] not in result


def test_apply_open_now_filter_unavailable_excluded(restaurant_set):
    r = _make_restaurant(
        name=f"TempClosed {_uid()}",
        is_temporarily_unavailable=True,
        hours_open=time(0, 0),
        hours_close=time(23, 59),
    )
    assert apply_open_now_filter([r]) == []
