import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from nomz.models import Restaurant, UserProfile

pytestmark = pytest.mark.django_db


def _create_user(username: str, role: str):
    user = User.objects.create_user(username=username, password="pass12345")
    UserProfile.objects.create(user=user, role=role)
    return user


def test_restaurant_claim_get_returns_empty_restaurant_list_for_owner():
    """
    Covers the GET block around lines 419-468 with an empty queryset branch.
    """
    client = APIClient()
    owner_user = _create_user("legacy_owner_empty", role="restaurant")
    client.force_login(owner_user)

    response = client.get("/api/restaurant-claim/?search=unknown")
    assert response.status_code == 200
    payload = response.json()
    assert payload["restaurants"] == []
    assert payload["recent_claims"] == []
    assert payload["active_claim"] is None


def test_restaurant_claim_post_large_ids_list_and_empty_list_validation():
    """
    Sends POST with a large list payload and an explicit empty list value
    to exercise form-validation error responses on this endpoint.
    """
    client = APIClient()
    owner_user = _create_user("legacy_owner_post", role="restaurant")
    client.force_login(owner_user)

    # Simulate "large list of IDs" input even though endpoint expects one restaurant_id.
    large_ids = list(range(1, 501))
    large_payload = {
        "restaurant_id": large_ids,
        "business_email": "owner@example.com",
        "contact_phone": "+1-212-555-1234",
        "proof_details": "bulk payload legacy simulation",
    }
    client.raise_request_exception = False
    large_response = client.post(
        "/api/restaurant-claim/",
        data=json.dumps(large_payload),
        content_type="application/json",
    )
    assert large_response.status_code == 500

    client.raise_request_exception = True

    # Explicit empty list input to trigger required/invalid selection path.
    empty_list_response = client.post(
        "/api/restaurant-claim/",
        data=json.dumps(
            {"restaurant_id": [], "business_email": "", "proof_details": ""}
        ),
        content_type="application/json",
    )
    assert empty_list_response.status_code == 400
    payload = empty_list_response.json()
    assert payload["success"] is False
    assert "errors" in payload
    assert "restaurant" in payload["errors"]


def test_restaurant_claim_post_internal_server_error_path():
    """
    Forces an unhandled exception inside form construction to assert a 500 response path.
    """
    client = APIClient()
    client.raise_request_exception = False
    owner_user = _create_user("legacy_owner_500", role="restaurant")
    client.force_login(owner_user)

    Restaurant.objects.create(
        name="Legacy Claim Spot",
        cuisine_type="other",
        price_range="$$",
    )

    with patch(
        "nomz.api_views.RestaurantOwnershipClaimForm",
        side_effect=Exception("forced internal error"),
    ):
        response = client.post(
            "/api/restaurant-claim/",
            data=json.dumps(
                {
                    "restaurant_id": 1,
                    "business_email": "owner@legacy.test",
                    "proof_details": "simulate server failure",
                }
            ),
            content_type="application/json",
        )

    assert response.status_code == 500
