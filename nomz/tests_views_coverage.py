from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings
from django.urls import path, reverse

from nomz.models import (
    FriendConversation,
    FriendMessage,
    FriendSharedRestaurant,
    ModerationReport,
    Restaurant,
    Review,
    UserProfile,
)
from nomz.views import (
    admin_recalculate_scores,
    admin_resolve_report,
    admin_toggle_user_status,
    create_group_chat,
    manage_group_member,
    message_restaurant,
    recommend_friend_restaurant,
    respond_to_review,
    toggle_shared_restaurant,
)


def _ok_view(_request, **_kwargs):
    return HttpResponse("ok")


urlpatterns = [
    path("landing/", _ok_view, name="landing"),
    path("dashboard/", _ok_view, name="dashboard"),
    path("profile/", _ok_view, name="profile"),
    path("moderation/", _ok_view, name="admin_moderation_dashboard"),
    path("friends/", _ok_view, name="friends_chat_index"),
    path("restaurant/<int:restaurant_id>/", _ok_view, name="restaurant_detail"),
    path(
        "messages/conversations/<int:conversation_id>/",
        _ok_view,
        name="conversation_detail",
    ),
    path("friends/<str:username>/", _ok_view, name="friends_chat_detail"),
    path(
        "friends/group/<int:conversation_id>/",
        _ok_view,
        name="friends_chat_detail_by_id",
    ),
    path("test/admin/recalculate/", admin_recalculate_scores, name="test_admin_recalc"),
    path(
        "test/admin/users/<int:user_id>/toggle/",
        admin_toggle_user_status,
        name="test_admin_toggle",
    ),
    path(
        "test/admin/moderation/<int:report_id>/resolve/",
        admin_resolve_report,
        name="test_admin_resolve_report",
    ),
    path(
        "test/friends/<str:username>/recommend/",
        recommend_friend_restaurant,
        name="test_recommend_friend_by_username",
    ),
    path(
        "test/friends/group/<int:conversation_id>/recommend/",
        recommend_friend_restaurant,
        name="test_recommend_friend_by_conversation",
    ),
    path(
        "test/messages/restaurant/<int:restaurant_id>/",
        message_restaurant,
        name="test_message_restaurant",
    ),
    path(
        "test/friends/group/create/",
        create_group_chat,
        name="test_create_group_chat",
    ),
    path(
        "test/friends/group/<int:conversation_id>/manage/",
        manage_group_member,
        name="test_manage_group_member",
    ),
    path(
        "test/friends/<str:username>/toggle-shared/",
        toggle_shared_restaurant,
        name="test_toggle_shared_by_username",
    ),
    path(
        "test/friends/group/<int:conversation_id>/toggle-shared/",
        toggle_shared_restaurant,
        name="test_toggle_shared_by_conversation",
    ),
    path(
        "test/reviews/<int:review_id>/respond/",
        respond_to_review,
        name="test_respond_to_review",
    ),
]


@override_settings(ROOT_URLCONF="nomz.tests_views_coverage")
class ViewsCoverageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username="staff_user",
            password="pass12345",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            username="root_admin",
            email="root@example.com",
            password="pass12345",
        )
        self.diner = User.objects.create_user(
            username="diner_user",
            password="pass12345",
        )
        self.reported_user = User.objects.create_user(
            username="reported_user",
            password="pass12345",
        )
        UserProfile.objects.create(user=self.diner, role="diner")
        UserProfile.objects.create(user=self.reported_user, role="diner")

    def _message_texts(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_admin_recalculate_scores_name_matching_error_paths(self):
        Restaurant.objects.create(name="Twin Name", cuisine_type="other", price_range="$$")
        Restaurant.objects.create(
            name="twin name",
            cuisine_type="other",
            price_range="$$",
        )
        Restaurant.objects.create(
            name="Partial Match One",
            cuisine_type="other",
            price_range="$$",
        )
        Restaurant.objects.create(
            name="Partial Match Two",
            cuisine_type="other",
            price_range="$$",
        )

        self.client.force_login(self.staff)

        duplicate_exact = self.client.post(
            reverse("test_admin_recalc"),
            {"restaurant_name": "Twin Name"},
            follow=True,
        )
        self.assertEqual(duplicate_exact.status_code, 200)
        self.assertTrue(
            any(
                "Multiple restaurants share that name" in txt
                for txt in self._message_texts(duplicate_exact)
            )
        )

        duplicate_partial = self.client.post(
            reverse("test_admin_recalc"),
            {"restaurant_name": "Partial"},
            follow=True,
        )
        self.assertEqual(duplicate_partial.status_code, 200)
        self.assertTrue(
            any(
                "Multiple restaurants match that name" in txt
                for txt in self._message_texts(duplicate_partial)
            )
        )

        no_match = self.client.post(
            reverse("test_admin_recalc"),
            {"restaurant_name": "Not Existing Anywhere"},
            follow=True,
        )
        self.assertEqual(no_match.status_code, 200)
        self.assertTrue(
            any("No restaurant found with that name." in txt for txt in self._message_texts(no_match))
        )

    def test_admin_toggle_user_status_permission_and_action_branches(self):
        target = User.objects.create_user(username="target_user", password="pass12345")
        other_super = User.objects.create_superuser(
            username="another_super",
            email="another@example.com",
            password="pass12345",
        )

        self.client.force_login(self.diner)
        forbidden = self.client.post(
            reverse("test_admin_toggle", args=[target.id]),
            {"action": "activate"},
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_login(self.staff)
        own_status = self.client.post(
            reverse("test_admin_toggle", args=[self.staff.id]),
            {"action": "deactivate"},
            follow=True,
        )
        self.assertTrue(
            any("cannot change your own status" in txt.lower() for txt in self._message_texts(own_status))
        )

        super_blocked = self.client.post(
            reverse("test_admin_toggle", args=[other_super.id]),
            {"action": "deactivate"},
            follow=True,
        )
        self.assertTrue(
            any("permission to change a superuser" in txt.lower() for txt in self._message_texts(super_blocked))
        )

        activate = self.client.post(
            reverse("test_admin_toggle", args=[target.id]),
            {"action": "activate"},
            follow=True,
        )
        target.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertTrue(any("Access ALLOWED" in txt for txt in self._message_texts(activate)))

        deactivate = self.client.post(
            reverse("test_admin_toggle", args=[target.id]),
            {"action": "deactivate"},
            follow=True,
        )
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertTrue(any("Access REVOKED" in txt for txt in self._message_texts(deactivate)))

        invalid = self.client.post(
            reverse("test_admin_toggle", args=[target.id]),
            {"action": "bogus"},
            follow=True,
        )
        self.assertTrue(any("Invalid action." in txt for txt in self._message_texts(invalid)))

    def test_admin_resolve_report_branches_for_review_and_user(self):
        restaurant = Restaurant.objects.create(
            name="Moderation Bistro",
            cuisine_type="other",
            price_range="$$",
        )
        review = Review.objects.create(
            restaurant=restaurant,
            user=self.diner,
            rating=3,
            comment="test review",
        )
        report_review = ModerationReport.objects.create(
            reporter=self.staff,
            review=review,
            reason="FRAUD",
            details="Looks fake",
        )
        report_user = ModerationReport.objects.create(
            reporter=self.staff,
            reported_user=self.reported_user,
            reason="HARASSMENT",
            details="Abusive behavior",
        )
        Restaurant.objects.create(
            name="Reported User Spot",
            owner=self.reported_user,
            cuisine_type="other",
            price_range="$$",
        )

        self.client.force_login(self.staff)

        dismiss = self.client.post(
            reverse("test_admin_resolve_report", args=[report_review.id]),
            {"action": "dismiss", "moderator_note": "No issue"},
            follow=True,
        )
        report_review.refresh_from_db()
        self.assertEqual(report_review.status, "DISMISSED")
        self.assertTrue(any("has been dismissed" in txt.lower() for txt in self._message_texts(dismiss)))

        flag_user = self.client.post(
            reverse("test_admin_resolve_report", args=[report_user.id]),
            {"action": "flag_fraud", "moderator_note": "fraud detected"},
            follow=True,
        )
        report_user.refresh_from_db()
        self.reported_user.userprofile.refresh_from_db()
        self.assertEqual(report_user.status, "RESOLVED")
        self.assertTrue(self.reported_user.userprofile.is_flagged)
        self.assertTrue(any("has been resolved" in txt.lower() for txt in self._message_texts(flag_user)))

        unflag_user = self.client.post(
            reverse("test_admin_resolve_report", args=[report_user.id]),
            {"action": "unflag", "moderator_note": "appeal granted"},
            follow=True,
        )
        self.reported_user.userprofile.refresh_from_db()
        report_user.refresh_from_db()
        self.assertEqual(report_user.status, "PENDING")
        self.assertFalse(self.reported_user.userprofile.is_flagged)
        self.assertTrue(any("has been pending" in txt.lower() for txt in self._message_texts(unflag_user)))

        delete_review = self.client.post(
            reverse("test_admin_resolve_report", args=[report_review.id]),
            {"action": "delete", "moderator_note": "remove content"},
            follow=True,
        )
        review.refresh_from_db()
        self.assertTrue(review.is_deleted)
        self.assertTrue(any("has been resolved" in txt.lower() for txt in self._message_texts(delete_review)))

        reevaluate = self.client.post(
            reverse("test_admin_resolve_report", args=[report_review.id]),
            {"action": "reevaluate", "moderator_note": "recheck"},
            follow=True,
        )
        report_review.refresh_from_db()
        self.assertEqual(report_review.status, "PENDING")
        self.assertTrue(any("has been pending" in txt.lower() for txt in self._message_texts(reevaluate)))

    def test_recommend_friend_restaurant_username_and_conversation_paths(self):
        friend = User.objects.create_user(username="friend_user", password="pass12345")
        UserProfile.objects.create(user=friend, role="diner")
        convo = FriendConversation.objects.create(
            user1=self.diner,
            user2=friend,
            is_group=False,
        )
        convo.participants.add(self.diner, friend)
        restaurant = Restaurant.objects.create(
            name="Shared Suggestion",
            cuisine_type="other",
            price_range="$$",
        )

        self.client.force_login(self.diner)

        by_username = self.client.post(
            reverse("test_recommend_friend_by_username", args=[friend.username]),
            {"restaurant_id": str(restaurant.id), "body": "Try this place"},
        )
        self.assertEqual(by_username.status_code, 302)
        self.assertEqual(by_username.url, reverse("friends_chat_detail", args=[friend.username]))
        self.assertEqual(FriendMessage.objects.filter(conversation=convo).count(), 1)

        no_restaurant = self.client.post(
            reverse("test_recommend_friend_by_conversation", args=[convo.id]),
            {"restaurant_name": "Not Existing"},
        )
        self.assertEqual(no_restaurant.status_code, 302)
        self.assertEqual(
            no_restaurant.url,
            reverse("friends_chat_detail_by_id", args=[convo.id]),
        )
        self.assertEqual(FriendMessage.objects.filter(conversation=convo).count(), 1)

        by_conversation = self.client.post(
            reverse("test_recommend_friend_by_conversation", args=[convo.id]),
            {"restaurant_name": "Shared Suggestion", "body": "name lookup"},
        )
        self.assertEqual(by_conversation.status_code, 302)
        self.assertEqual(
            by_conversation.url,
            reverse("friends_chat_detail_by_id", args=[convo.id]),
        )
        self.assertEqual(FriendMessage.objects.filter(conversation=convo).count(), 2)

    def test_respond_to_review_invalid_post_shows_error_message(self):
        owner = User.objects.create_user(username="owner_user", password="pass12345")
        UserProfile.objects.create(user=owner, role="restaurant", is_approved=True)
        restaurant = Restaurant.objects.create(
            owner=owner,
            name="Owner View Bistro",
            cuisine_type="other",
            price_range="$$",
        )
        review = Review.objects.create(
            restaurant=restaurant,
            user=self.diner,
            rating=4,
            comment="nice",
        )

        self.client.force_login(owner)
        response = self.client.post(
            reverse("test_respond_to_review", args=[review.id]),
            {"response_text": ""},  # invalid -> form.is_valid() == False
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "Could not save response" in txt
                for txt in self._message_texts(response)
            )
        )

    def test_message_restaurant_post_error_feedback_branches(self):
        # branch: restaurant owner account cannot start diner->restaurant convo
        owner_user = User.objects.create_user(username="owner_sender", password="pass12345")
        UserProfile.objects.create(user=owner_user, role="restaurant", is_approved=True)
        target_owner = User.objects.create_user(username="target_owner", password="pass12345")
        UserProfile.objects.create(user=target_owner, role="restaurant", is_approved=True)
        target_restaurant = Restaurant.objects.create(
            owner=target_owner,
            name="Target Msg Spot",
            cuisine_type="other",
            price_range="$$",
            messaging_enabled=True,
        )
        self.client.force_login(owner_user)
        owner_blocked = self.client.post(
            reverse("test_message_restaurant", args=[target_restaurant.id]),
            {"message": ""},
            follow=True,
        )
        self.assertEqual(owner_blocked.status_code, 200)
        self.assertTrue(
            any("cannot start a diner-to-restaurant conversation" in t.lower() for t in self._message_texts(owner_blocked))
        )

        # branch: restaurant has no owner
        self.client.force_login(self.diner)
        unowned = Restaurant.objects.create(
            name="Unowned Spot",
            cuisine_type="other",
            price_range="$$",
        )
        no_owner = self.client.post(
            reverse("test_message_restaurant", args=[unowned.id]),
            {"message": "hello"},
            follow=True,
        )
        self.assertEqual(no_owner.status_code, 200)
        self.assertTrue(
            any("does not yet have an owner account" in t.lower() for t in self._message_texts(no_owner))
        )

        # branch: messaging disabled
        disabled_owner = User.objects.create_user(
            username="disabled_owner",
            password="pass12345",
        )
        UserProfile.objects.create(user=disabled_owner, role="restaurant", is_approved=True)
        disabled = Restaurant.objects.create(
            owner=disabled_owner,
            name="Disabled Msg Spot",
            cuisine_type="other",
            price_range="$$",
            messaging_enabled=False,
        )
        disabled_response = self.client.post(
            reverse("test_message_restaurant", args=[disabled.id]),
            {"message": "hello"},
            follow=True,
        )
        self.assertEqual(disabled_response.status_code, 200)
        self.assertTrue(
            any("messaging disabled" in t.lower() for t in self._message_texts(disabled_response))
        )

    def test_manage_group_member_permission_and_action_paths(self):
        creator = User.objects.create_user(username="group_creator", password="pass12345")
        UserProfile.objects.create(user=creator, role="diner")
        outsider = User.objects.create_user(username="group_outsider", password="pass12345")
        UserProfile.objects.create(user=outsider, role="diner")
        restaurant_role_user = User.objects.create_user(username="biz_member", password="pass12345")
        UserProfile.objects.create(user=restaurant_role_user, role="restaurant")
        diner_member = User.objects.create_user(username="diner_member", password="pass12345")
        UserProfile.objects.create(user=diner_member, role="diner")

        conv = FriendConversation.objects.create(
            name="Coverage Group",
            is_group=True,
            creator=creator,
        )
        conv.participants.add(creator)

        self.client.force_login(outsider)
        forbidden_manage = self.client.post(
            reverse("test_manage_group_member", args=[conv.id]),
            {"action": "add", "user_id": diner_member.id},
            follow=True,
        )
        self.assertEqual(forbidden_manage.status_code, 200)
        self.assertTrue(
            any("only the group creator can manage members" in t.lower() for t in self._message_texts(forbidden_manage))
        )

        self.client.force_login(creator)
        add_non_diner = self.client.post(
            reverse("test_manage_group_member", args=[conv.id]),
            {"action": "add", "user_id": restaurant_role_user.id},
            follow=True,
        )
        self.assertEqual(add_non_diner.status_code, 200)
        self.assertTrue(
            any("only diners can be added" in t.lower() for t in self._message_texts(add_non_diner))
        )

        remove_creator = self.client.post(
            reverse("test_manage_group_member", args=[conv.id]),
            {"action": "remove", "user_id": creator.id},
            follow=True,
        )
        self.assertEqual(remove_creator.status_code, 200)
        self.assertTrue(
            any("cannot remove yourself" in t.lower() for t in self._message_texts(remove_creator))
        )

    def test_toggle_shared_restaurant_redirect_and_not_owned_access(self):
        friend = User.objects.create_user(username="toggle_friend", password="pass12345")
        UserProfile.objects.create(user=friend, role="diner")
        outsider = User.objects.create_user(username="toggle_outsider", password="pass12345")
        UserProfile.objects.create(user=outsider, role="diner")
        restaurant = Restaurant.objects.create(
            name="Toggle Spot",
            cuisine_type="other",
            price_range="$$",
        )
        convo = FriendConversation.objects.create(user1=self.diner, user2=friend, is_group=False)
        convo.participants.add(self.diner, friend)

        # User attempts username-route access to a chat they do not own -> 404 (permission by lookup constraints).
        self.client.force_login(outsider)
        not_owned = self.client.post(
            reverse("test_toggle_shared_by_username", args=[friend.username]),
            {"restaurant_name": restaurant.name, "action": "add"},
        )
        self.assertEqual(not_owned.status_code, 404)

        # Owner of conversation can add/remove via conversation route and gets redirect response.
        self.client.force_login(self.diner)
        added = self.client.post(
            reverse("test_toggle_shared_by_conversation", args=[convo.id]),
            {"restaurant_name": restaurant.name, "action": "add"},
        )
        self.assertEqual(added.status_code, 302)
        self.assertEqual(added.url, reverse("friends_chat_detail_by_id", args=[convo.id]))
        self.assertTrue(
            FriendSharedRestaurant.objects.filter(conversation=convo, restaurant=restaurant).exists()
        )

        removed = self.client.post(
            reverse("test_toggle_shared_by_conversation", args=[convo.id]),
            {"restaurant_id": restaurant.id, "action": "remove"},
        )
        self.assertEqual(removed.status_code, 302)
        self.assertEqual(removed.url, reverse("friends_chat_detail_by_id", args=[convo.id]))
        self.assertFalse(
            FriendSharedRestaurant.objects.filter(conversation=convo, restaurant=restaurant).exists()
        )

    def test_create_group_chat_post_invalid_and_valid_data(self):
        self.client.force_login(self.diner)
        participant = User.objects.create_user(
            username="group_participant_diner",
            password="pass12345",
        )
        UserProfile.objects.create(user=participant, role="diner")

        # Invalid branch: empty group name -> error + redirect.
        invalid = self.client.post(
            reverse("test_create_group_chat"),
            {"group_name": "", "participants": [str(participant.id)]},
            follow=True,
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertTrue(
            any("group name is required" in t.lower() for t in self._message_texts(invalid))
        )

        # Valid branch: group is created and redirects to detail.
        valid = self.client.post(
            reverse("test_create_group_chat"),
            {"group_name": "Coverage Group", "participants": [str(participant.id)]},
        )
        self.assertEqual(valid.status_code, 302)
        created = FriendConversation.objects.filter(
            is_group=True, name="Coverage Group", creator=self.diner
        ).first()
        self.assertIsNotNone(created)
        self.assertTrue(created.participants.filter(id=self.diner.id).exists())
        self.assertTrue(created.participants.filter(id=participant.id).exists())

    def test_manage_group_member_non_owner_permission_error(self):
        creator = User.objects.create_user(
            username="manage_creator_x",
            password="pass12345",
        )
        UserProfile.objects.create(user=creator, role="diner")
        conv = FriendConversation.objects.create(
            name="Manage Group X",
            is_group=True,
            creator=creator,
        )
        conv.participants.add(creator)

        self.client.force_login(self.diner)  # not the creator
        denied = self.client.post(
            reverse("test_manage_group_member", args=[conv.id]),
            {"action": "add", "username": "nobody"},
            follow=True,
        )
        self.assertEqual(denied.status_code, 200)
        self.assertTrue(
            any("only the group creator can manage members" in t.lower() for t in self._message_texts(denied))
        )
