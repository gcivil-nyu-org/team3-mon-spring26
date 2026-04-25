"""
Tests for legacy JSON views in nomz.api_views (non-DRF paths under nomz.urls).
"""

import uuid

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from nomz.models import Restaurant, RestaurantOwnershipClaim, UserProfile


@pytest.mark.django_db
def test_api_restaurant_claim_get_hits_claim_state_and_catalog_block():
    """
    Covers api_views.restaurant_claim_api GET (lines ~425–479): has_restaurant,
    active pending claim lookup, search_query, RestaurantOwnershipClaimForm
    queryset iteration (address_parts / joined address), and recent_claims.

    Endpoint: GET /api/restaurant-claim/ — name api_restaurant_claim.
    Access is @login_required plus role restaurant via UserProfile (not staff);
    we use force_login with a real restaurant-role user.
    """
    suffix = uuid.uuid4().hex[:10]
    user = User.objects.create_user(
        username=f"claim_owner_{suffix}", password="test-pass-123"
    )
    UserProfile.objects.create(user=user, role="restaurant", is_approved=True)

    r_full = Restaurant.objects.create(
        name=f"0ClaimFull{suffix}",
        owner=None,
        address="100 Main St",
        borough="Brooklyn",
        zip_code="11201",
    )
    r_zip_only = Restaurant.objects.create(
        name=f"0ClaimZip{suffix}",
        owner=None,
        address="",
        borough="",
        zip_code="10002",
    )
    r_blank_address = Restaurant.objects.create(
        name=f"0ClaimGhost{suffix}",
        owner=None,
        address=None,
        borough="",
        zip_code="",
    )
    past_target = Restaurant.objects.create(
        name=f"0ClaimPast{suffix}",
        owner=None,
        zip_code="10004",
    )
    RestaurantOwnershipClaim.objects.create(
        claimant=user,
        restaurant=past_target,
        status=RestaurantOwnershipClaim.STATUS_APPROVED,
    )
    pending_target = Restaurant.objects.create(
        name=f"0ClaimPending{suffix}",
        owner=None,
        zip_code="10003",
    )
    pending = RestaurantOwnershipClaim.objects.create(
        claimant=user,
        restaurant=pending_target,
        status=RestaurantOwnershipClaim.STATUS_PENDING,
    )

    client = Client()
    client.force_login(user)
    url = reverse("api_restaurant_claim")

    resp = client.get(url, {"search": f"Pending{suffix}"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_restaurant"] is False
    assert data["eligible"] is True
    assert data["search_query"] == f"Pending{suffix}"
    assert data["active_claim"] is not None
    assert data["active_claim"]["id"] == pending.id
    assert data["active_claim"]["restaurant_id"] == pending_target.id
    assert data["active_claim"]["status"] == RestaurantOwnershipClaim.STATUS_PENDING

    names = {r["name"] for r in data["restaurants"]}
    assert f"0ClaimPending{suffix}" in names

    recent_ids = {c["id"] for c in data["recent_claims"]}
    assert pending.id in recent_ids
    assert any(c["restaurant_name"] == past_target.name for c in data["recent_claims"])

    resp_all = client.get(url)
    assert resp_all.status_code == 200
    catalog = {r["id"]: r for r in resp_all.json()["restaurants"]}

    assert catalog[r_full.id]["address"] == "100 Main St, Brooklyn, 11201"
    assert catalog[r_zip_only.id]["address"] == "10002"
    assert catalog[r_zip_only.id]["zip_code"] == "10002"
    assert catalog[r_blank_address.id]["address"] == ""
    assert catalog[r_blank_address.id]["zip_code"] == ""
