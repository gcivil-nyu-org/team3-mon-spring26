from django.urls import path
from django.views.generic import RedirectView

from . import api_views, spa_api, views, html_views

# --- Health & JSON API (unchanged paths) ---------------------------------
urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path(
        "api/restaurants/map-data/",
        api_views.map_restaurant_data,
        name="api_restaurants_map",
    ),
    path(
        "api/messages/conversations/",
        api_views.list_conversations,
        name="api_conversation_list",
    ),
    path(
        "api/messages/conversations/start/",
        api_views.start_conversation,
        name="api_conversation_start",
    ),
    path(
        "api/messages/conversations/<int:conversation_id>/",
        api_views.conversation_messages,
        name="api_conversation_messages",
    ),
    path(
        "api/messages/conversations/<int:conversation_id>/send/",
        api_views.send_message,
        name="api_send_message",
    ),
    path(
        "api/restaurant-claim/",
        api_views.restaurant_claim_api,
        name="api_restaurant_claim",
    ),
    path("api/auth/session/", spa_api.auth_session, name="api_auth_session"),
    path("api/auth/register/", spa_api.auth_register, name="api_auth_register"),
    path("api/auth/login/", spa_api.auth_login, name="api_auth_login"),
    path(
        "api/auth/admin-login/", spa_api.auth_admin_login, name="api_auth_admin_login"
    ),
    path("api/auth/logout/", spa_api.auth_logout, name="api_auth_logout"),
    path("api/auth/2fa/verify/", spa_api.auth_2fa_verify, name="api_auth_2fa_verify"),
    path(
        "api/auth/password-reset/",
        spa_api.auth_password_reset_request,
        name="api_auth_password_reset",
    ),
    path(
        "api/auth/password-reset/confirm/",
        spa_api.auth_password_reset_confirm,
        name="api_auth_password_reset_confirm",
    ),
    path(
        "api/restaurant/photos/data/",
        spa_api.restaurant_photos_data,
        name="api_restaurant_photos_data",
    ),
    path(
        "api/restaurant/photos/upload/",
        spa_api.restaurant_photo_upload,
        name="api_restaurant_photo_upload",
    ),
    path(
        "api/restaurant/photos/<int:photo_id>/delete/",
        spa_api.restaurant_photo_delete,
        name="api_restaurant_photo_delete",
    ),
    path(
        "api/restaurant/photos/<int:photo_id>/set-primary/",
        spa_api.restaurant_photo_set_primary,
        name="api_restaurant_photo_set_primary",
    ),
    path(
        "api/restaurant/activation/",
        spa_api.restaurant_activation_api,
        name="api_restaurant_activation",
    ),
    path(
        "api/diner/preferences/",
        spa_api.diner_preferences_api,
        name="api_diner_preferences",
    ),
    path(
        "api/diner/account/",
        spa_api.diner_account_api,
        name="api_diner_account",
    ),
    path(
        "api/admin/dashboard-summary/",
        spa_api.admin_dashboard_summary,
        name="api_admin_dashboard_summary",
    ),
    path(
        "api/admin/pending-approvals/",
        spa_api.admin_pending_approvals_data,
        name="api_admin_pending_approvals_data",
    ),
    path(
        "api/admin/approved-restaurants/",
        spa_api.admin_approved_restaurant_accounts_data,
        name="api_admin_approved_restaurants",
    ),
    path(
        "api/admin/rejected-restaurants/",
        spa_api.admin_rejected_restaurant_accounts_data,
        name="api_admin_rejected_restaurants",
    ),
    path(
        "api/admin/approve/<int:user_id>/",
        spa_api.admin_approve_user_api,
        name="api_admin_approve_user",
    ),
    path(
        "api/admin/reject/<int:user_id>/",
        spa_api.admin_reject_user_api,
        name="api_admin_reject_user",
    ),
    path(
        "api/admin/moderation/",
        spa_api.admin_moderation_data,
        name="api_admin_moderation_data",
    ),
    path(
        "api/admin/moderation/reports/<int:report_id>/resolve/",
        spa_api.admin_resolve_report_api,
        name="api_admin_resolve_report_api",
    ),
    path(
        "api/admin/users/",
        spa_api.admin_users_data,
        name="api_admin_users_data",
    ),
    path(
        "api/admin/users/<int:user_id>/toggle-active/",
        spa_api.admin_toggle_user_active_api,
        name="api_admin_toggle_user_active",
    ),
    path(
        "api/admin/login-logs/",
        spa_api.admin_login_logs_data,
        name="api_admin_login_logs_data",
    ),
    path(
        "api/restaurants/<int:restaurant_id>/",
        spa_api.restaurant_detail_data,
        name="api_restaurant_detail",
    ),
    path(
        "api/restaurants/<int:restaurant_id>/review/",
        spa_api.restaurant_add_review,
        name="api_restaurant_add_review",
    ),
    path(
        "api/report/",
        spa_api.report_content_api,
        name="api_report_content",
    ),
    path("api/search/", spa_api.restaurant_search_api, name="api_restaurant_search"),
    path(
        "api/recommendations/",
        spa_api.diner_recommendations_api,
        name="api_diner_recommendations",
    ),
    path(
        "api/restaurant/profile/",
        spa_api.restaurant_profile_api,
        name="api_restaurant_profile",
    ),
    path(
        "api/restaurant/availability/",
        spa_api.restaurant_availability_api,
        name="api_restaurant_availability",
    ),
    path(
        "api/restaurant/communication/",
        spa_api.restaurant_communication_api,
        name="api_restaurant_communication",
    ),
    path(
        "api/restaurant/performance/",
        spa_api.restaurant_performance_api,
        name="api_restaurant_performance",
    ),
    path(
        "api/reviews/<int:review_id>/respond/",
        spa_api.review_respond_api,
        name="api_review_respond",
    ),
    path(
        "api/admin/recalculate-scores/",
        spa_api.admin_recalculate_scores_api,
        name="api_admin_recalculate_scores",
    ),
    path(
        "api/admin/score-anomalies/",
        spa_api.admin_score_anomalies_api,
        name="api_admin_score_anomalies",
    ),
    path(
        "api/admin/score-anomalies/<int:anomaly_id>/resolve/",
        spa_api.admin_resolve_score_anomaly_api,
        name="api_admin_resolve_score_anomaly",
    ),
    # --- Friend Chat API ---------------------------------------------------
    path(
        "api/friends-chat/",
        spa_api.friends_chat_list_api,
        name="api_friends_chat_list",
    ),
    path(
        "api/friends-chat/<int:conversation_id>/",
        spa_api.friends_chat_detail_api,
        name="api_friends_chat_detail",
    ),
    path(
        "api/friends-chat/group/create/",
        spa_api.friends_chat_group_create_api,
        name="api_friends_chat_group_create",
    ),
    path(
        "api/friends-chat/group/<int:conversation_id>/manage/",
        spa_api.friends_chat_group_manage_api,
        name="api_friends_chat_group_manage",
    ),
    path(
        "api/friends-chat/group/<int:conversation_id>/leave/",
        spa_api.friends_chat_group_leave_api,
        name="api_friends_chat_group_leave",
    ),
    path(
        "api/friends-chat/<int:conversation_id>/recommend/",
        spa_api.friends_chat_recommend_api,
        name="api_friends_chat_recommend",
    ),
    path(
        "api/friends-chat/<int:conversation_id>/toggle-shared/",
        spa_api.friends_chat_toggle_shared_api,
        name="api_friends_chat_toggle_shared",
    ),
    path(
        "api/friends-chat/search-users/",
        spa_api.friends_chat_search_users_api,
        name="api_friends_chat_search_users",
    ),
]

# --- Server-side views (POST actions that redirect) -------------------------
urlpatterns += [
    path(
        "nomz-admin/recalculate-scores/",
        views.admin_recalculate_scores,
        name="admin_recalculate_scores",
    ),
    path(
        "nomz-admin/score-anomalies/<int:anomaly_id>/resolve/",
        views.admin_resolve_score_anomaly,
        name="admin_resolve_score_anomaly",
    ),
    path(
        "reviews/<int:review_id>/respond/",
        views.respond_to_review,
        name="respond_to_review",
    ),
]

# --- Short redirects kept for old bookmarks --------------------------------
urlpatterns += [
    path(
        "dashboard/search/",
        RedirectView.as_view(url="/search/", permanent=False),
        name="restaurant_search_dashboard_alias",
    ),
    path(
        "dashboard/Admin-login/",
        RedirectView.as_view(url="/admin-login/", permanent=False),
    ),
    path(
        "dashboard/admin-login/",
        RedirectView.as_view(url="/admin-login/", permanent=False),
    ),
]

# ==============================================================================
# HTML TEMPLATE VIEWS (Replacing React SPA)
# ==============================================================================

# Public pages
urlpatterns += [
    path("", html_views.home, name="landing"),
    path("home/", html_views.home, name="home"),
]

# Authentication pages
urlpatterns += [
    path("signin/", html_views.signin, name="signin"),
    path("register/", html_views.signup, name="register"),
    path("logout/", html_views.logout_view, name="logout"),
    path("password-reset/", html_views.password_reset, name="password_reset"),
    path(
        "password-reset/done/",
        html_views.password_reset_done,
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/",
        html_views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        html_views.password_reset_complete,
        name="password_reset_complete",
    ),
    path(
        "reset/<uidb64>/<token>/",
        html_views.password_reset_confirm,
        name="password_reset_confirm_link",
    ),
    path(
        "reset/done/",
        html_views.password_reset_complete,
        name="password_reset_complete_legacy",
    ),
    path("admin-login/", html_views.admin_login, name="admin_login"),
]

# Dashboard (smart router)
urlpatterns += [
    path("dashboard/", html_views.dashboard, name="dashboard"),
]

# Diner pages
urlpatterns += [
    path("map/", html_views.map_view, name="map"),
    path("search/", html_views.search_results, name="restaurant_search"),
    path("profile/", html_views.user_profile, name="profile"),
    path("preferences/", html_views.manage_preferences, name="manage_preferences"),
    path("recommendations/", html_views.recommendations, name="recommendations"),
    path(
        "restaurant/<int:restaurant_id>/",
        html_views.restaurant_detail,
        name="restaurant_detail",
    ),
    path(
        "restaurant/<int:restaurant_id>/review/",
        html_views.add_review,
        name="add_review",
    ),
    path("messages/", html_views.messages_view, name="message_inbox"),
    path(
        "messages/restaurant/<int:restaurant_id>/",
        html_views.start_message,
        name="message_restaurant",
    ),
    path(
        "messages/conversations/<int:conversation_id>/",
        html_views.message_thread,
        name="conversation_detail",
    ),
    path(
        "report/<str:content_type>/<int:content_id>/",
        html_views.report_content,
        name="report_content",
    ),
]

# Friends chat
urlpatterns += [
    path("friends-chat/", html_views.friends_chat, name="friends_chat_html"),
    # Alias: /friends/ → /friends-chat/ (used by nav links in dashboard/map)
    path(
        "friends/",
        RedirectView.as_view(url="/friends-chat/", permanent=False),
        name="friends_redirect",
    ),
]

# Restaurant owner pages
urlpatterns += [
    path(
        "restaurant-profile/", html_views.restaurant_profile, name="restaurant_profile"
    ),
    path("restaurant/photos/", html_views.photo_management, name="restaurant_photos"),
    path("restaurant/photos/upload/", html_views.upload_photo, name="upload_photo"),
    path("restaurant/claim/", html_views.claim_restaurant, name="claim_restaurant"),
    path("restaurant/create/", html_views.create_restaurant, name="create_restaurant"),
    path("restaurant/edit/", html_views.edit_restaurant, name="edit_restaurant"),
    path(
        "restaurant/availability/",
        html_views.manage_availability,
        name="manage_availability",
    ),
    path(
        "restaurant/activate/", html_views.manage_activation, name="manage_activation"
    ),
    path(
        "restaurant/communication/",
        html_views.manage_communication_settings,
        name="manage_communication_settings",
    ),
    path("restaurant/map/", html_views.restaurant_map, name="restaurant_map"),
]

# Admin pages
urlpatterns += [
    path("nomz-admin/", html_views.admin_dashboard, name="admin_dashboard"),
    path("nomz-admin/map/", html_views.admin_map, name="admin_map"),
    path(
        "nomz-admin/moderation/",
        html_views.admin_moderation,
        name="admin_moderation_dashboard",
    ),
    path(
        "nomz-admin/moderation/resolve/<int:report_id>/",
        html_views.resolve_report,
        name="admin_resolve_report",
    ),
    path(
        "nomz-admin/pending-approvals/",
        html_views.pending_approvals,
        name="admin_pending_approvals",
    ),
    path("nomz-admin/users/", html_views.manage_users, name="admin_manage_users"),
    path("nomz-admin/logs/", html_views.admin_logs, name="admin_login_logs"),
    path(
        "nomz-admin/approved-accounts/",
        html_views.approved_accounts,
        name="admin_approved_accounts",
    ),
    path(
        "nomz-admin/rejected-accounts/",
        html_views.rejected_accounts,
        name="admin_rejected_accounts",
    ),
]

# --- Modernized Friend Chat Route Overrides ---
# These overrides point existing URL names and paths to the modernized v2 views.
# They are inserted at the beginning of the list to ensure they take precedence.
urlpatterns.insert(
    0, path("friends-chat/", views.friends_chat_index_v2, name="friends_chat_index")
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/group/create/",
        views.create_group_chat_v2,
        name="create_group_chat",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/group/<int:conversation_id>/manage/",
        views.manage_group_member_v2,
        name="manage_group_member",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/group/<int:conversation_id>/leave/",
        views.leave_group_v2,
        name="leave_group",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/group/<int:conversation_id>/recommend/",
        views.recommend_friend_restaurant_v2,
        name="recommend_friend_restaurant_by_id",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/group/<int:conversation_id>/toggle-shared/",
        views.toggle_shared_restaurant_v2,
        name="toggle_shared_restaurant_by_id",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/group/<int:conversation_id>/",
        views.friends_chat_detail_v2,
        name="friends_chat_detail_by_id",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/<str:username>/recommend/",
        views.recommend_friend_restaurant_v2,
        name="recommend_friend_restaurant",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/<str:username>/toggle-shared/",
        views.toggle_shared_restaurant_v2,
        name="toggle_shared_restaurant",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat/<str:username>/",
        views.friends_chat_detail_v2,
        name="friends_chat_detail",
    ),
)

# Also register the v2 names for use in modernized templates
urlpatterns.insert(
    0,
    path("friends-chat-v2/", views.friends_chat_index_v2, name="friends_chat_index_v2"),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/group/create/",
        views.create_group_chat_v2,
        name="create_group_chat_v2",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/group/<int:conversation_id>/manage/",
        views.manage_group_member_v2,
        name="manage_group_member_v2",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/group/<int:conversation_id>/leave/",
        views.leave_group_v2,
        name="leave_group_v2",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/group/<int:conversation_id>/recommend/",
        views.recommend_friend_restaurant_v2,
        name="recommend_friend_restaurant_v2_by_id",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/group/<int:conversation_id>/toggle-shared/",
        views.toggle_shared_restaurant_v2,
        name="toggle_shared_restaurant_v2_by_id",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/group/<int:conversation_id>/",
        views.friends_chat_detail_v2,
        name="friends_chat_detail_v2_by_id",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/<str:username>/recommend/",
        views.recommend_friend_restaurant_v2,
        name="recommend_friend_restaurant_v2",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/<str:username>/toggle-shared/",
        views.toggle_shared_restaurant_v2,
        name="toggle_shared_restaurant_v2",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/<str:username>/",
        views.friends_chat_detail_v2,
        name="friends_chat_detail_v2",
    ),
)
urlpatterns.insert(
    0,
    path(
        "friends-chat-v2/seed/", views.seed_restaurants_v2, name="seed_restaurants_v2"
    ),
)
urlpatterns.insert(
    0,
    path(
        "api/restaurants/search-v2/",
        views.restaurant_search_api_v2,
        name="restaurant_search_api_v2",
    ),
)
urlpatterns.insert(
    0,
    path("api/diner-search-v2/", views.diner_search_api_v2, name="diner_search_api_v2"),
)
