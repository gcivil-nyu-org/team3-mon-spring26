from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from unittest.mock import patch

from nomz.admin import RestaurantOwnershipClaimAdmin
from nomz.models import Restaurant, RestaurantOwnershipClaim, UserProfile


class AdminActionsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = RestaurantOwnershipClaimAdmin(RestaurantOwnershipClaim, self.site)
        self.staff = User.objects.create_user(
            username="admin_actor",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )

    def _request_with_messages(self):
        request = self.factory.post("/admin/nomz/restaurantownershipclaim/")
        request.user = self.staff
        request.session = self.client.session
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def test_approve_selected_claims_handles_validation_error_and_success_message(self):
        claimant = User.objects.create_user(username="claimant", password="pass12345")
        UserProfile.objects.create(user=claimant, role="restaurant")
        restaurant = Restaurant.objects.create(
            name="Admin Action Bistro",
            cuisine_type="other",
            price_range="$$",
        )
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=claimant,
            restaurant=restaurant,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        )

        request = self._request_with_messages()
        # Force the ValidationError branch inside lines 145-150.
        with patch.object(
            RestaurantOwnershipClaim,
            "approve",
            side_effect=ValidationError("blocked by test"),
        ):
            self.admin.approve_selected_claims(
                request, RestaurantOwnershipClaim.objects.filter(id=claim.id)
            )

        msg_texts = [str(m) for m in get_messages(request)]
        assert any("Could not approve claim" in t for t in msg_texts)
        assert any("Approved 0 claim(s)." in t for t in msg_texts)

    def test_approve_selected_claims_skips_non_pending(self):
        claimant = User.objects.create_user(username="claimant2", password="pass12345")
        UserProfile.objects.create(user=claimant, role="restaurant")
        restaurant = Restaurant.objects.create(
            name="Already Reviewed Spot",
            cuisine_type="other",
            price_range="$$",
        )
        claim = RestaurantOwnershipClaim.objects.create(
            claimant=claimant,
            restaurant=restaurant,
            status=RestaurantOwnershipClaim.STATUS_APPROVED,
        )
        request = self._request_with_messages()
        self.admin.approve_selected_claims(
            request, RestaurantOwnershipClaim.objects.filter(id=claim.id)
        )
        msg_texts = [str(m) for m in get_messages(request)]
        assert any("Approved 0 claim(s)." in t for t in msg_texts)
