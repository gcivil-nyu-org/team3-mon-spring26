"""
Admin integration tests for custom ``ModelAdmin`` actions in ``nomz.admin``.

Lines 138–161 apply to ``RestaurantOwnershipClaimAdmin`` (approve / reject bulk
actions), not Django's default delete on ``Restaurant``.
"""

import uuid

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from nomz.models import Restaurant, RestaurantOwnershipClaim, UserProfile


@pytest.mark.django_db
def test_admin_bulk_approve_and_reject_ownership_claim_actions(admin_client):
    """Exercise ``approve_selected_claims`` (~138–151) and ``reject_selected_claims`` (~155–161)."""
    suffix = uuid.uuid4().hex[:8]
    url = reverse("admin:nomz_restaurantownershipclaim_changelist")

    def _claim_setup(prefix: str):
        claimant = User.objects.create_user(
            username=f"{prefix}_claimant_{suffix}",
            password="pw-test-123",
        )
        UserProfile.objects.create(user=claimant, role="restaurant", is_approved=True)
        restaurant = Restaurant.objects.create(
            name=f"{prefix}_Rest_{suffix}",
            owner=None,
            is_active=True,
        )
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=claimant,
            restaurant=restaurant,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
            business_email=f"{prefix}_{suffix}@example.com",
            contact_phone="2125550000",
            proof_details="Test proof",
        )
        return claim

    c1 = _claim_setup("ap1")
    c2 = _claim_setup("ap2")
    resp = admin_client.post(
        url,
        {
            "action": "approve_selected_claims",
            "_selected_action": [str(c1.pk), str(c2.pk)],
        },
    )
    assert resp.status_code in (200, 302)
    c1.refresh_from_db()
    c2.refresh_from_db()
    assert c1.status == RestaurantOwnershipClaim.STATUS_APPROVED
    assert c2.status == RestaurantOwnershipClaim.STATUS_APPROVED

    r1 = _claim_setup("rj1")
    r2 = _claim_setup("rj2")
    resp_rej = admin_client.post(
        url,
        {
            "action": "reject_selected_claims",
            "_selected_action": [str(r1.pk), str(r2.pk)],
        },
    )
    assert resp_rej.status_code in (200, 302)
    r1.refresh_from_db()
    r2.refresh_from_db()
    assert r1.status == RestaurantOwnershipClaim.STATUS_REJECTED
    assert r2.status == RestaurantOwnershipClaim.STATUS_REJECTED
