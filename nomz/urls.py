from django.urls import path, re_path
from django.views.generic import RedirectView

from . import api_views, spa_api, spa_shell_views, views

# --- Health & JSON API (unchanged paths) ---------------------------------
urlpatterns = [
    # Vite hashed files under /assets/ (must stay ahead of SPA catch-alls)
    path(
        "assets/<path:asset_path>",
        spa_shell_views.spa_asset,
        name="spa_asset",
    ),
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

# --- Legacy URL names → same SPA shell (React is the main UI) --------------
_SPA_NAMED = [
    ("", "landing"),
    ("home/", "home"),
    ("signin/", "signin"),
    ("map/", "map"),
    ("register/", "register"),
    ("logout/", "logout"),
    ("profile/", "profile"),
    ("dashboard/", "dashboard"),
    ("restaurant-profile/", "restaurant_profile"),
    ("search/", "restaurant_search"),
    ("preferences/", "manage_preferences"),
    ("recommendations/", "recommendations"),
    ("restaurant/claim/", "claim_restaurant"),
    ("restaurant/create/", "create_restaurant"),
    ("restaurant/edit/", "edit_restaurant"),
    ("restaurant/availability/", "manage_availability"),
    ("restaurant/activate/", "manage_activation"),
    ("restaurant/communication/", "manage_communication_settings"),
    ("restaurant/photos/", "restaurant_photos"),
    ("restaurant/photos/upload/", "upload_photo"),
    ("restaurant/photos/<int:photo_id>/delete/", "delete_photo"),
    ("restaurant/photos/<int:photo_id>/set-primary/", "set_primary_photo"),
    ("password-reset/", "password_reset"),
    ("password-reset/done/", "password_reset_done"),
    ("reset/<uidb64>/<token>/", "password_reset_confirm"),
    ("reset/done/", "password_reset_complete"),
    ("admin-login/", "admin_login"),
    ("nomz-admin/logs/", "admin_login_logs"),
    ("nomz-admin/users/", "admin_manage_users"),
    ("nomz-admin/users/<int:user_id>/toggle/", "toggle_user_status"),
    ("nomz-admin/approved-accounts/", "admin_approved_accounts"),
    ("nomz-admin/rejected-accounts/", "admin_rejected_accounts"),
    ("nomz-admin/pending-approvals/", "admin_pending_approvals"),
    ("nomz-admin/approve/<int:user_id>/", "admin_approve_restaurant"),
    ("nomz-admin/reject/<int:user_id>/", "admin_reject_restaurant"),
    ("restaurant/<int:restaurant_id>/review/", "add_review"),
    ("restaurant/<int:restaurant_id>/", "restaurant_detail"),
    # Friends chat (React + /api/friends-chat/); order matters vs <str:username>
    ("friends-chat/", "friends_chat_index"),
    ("friends-chat/group/create/", "create_group_chat"),
    (
        "friends-chat/group/<int:conversation_id>/manage/",
        "manage_group_member",
    ),
    ("friends-chat/group/<int:conversation_id>/leave/", "leave_group"),
    (
        "friends-chat/group/<int:conversation_id>/recommend/",
        "recommend_friend_restaurant_by_id",
    ),
    (
        "friends-chat/group/<int:conversation_id>/toggle-shared/",
        "toggle_shared_restaurant_by_id",
    ),
    ("friends-chat/group/<int:conversation_id>/", "friends_chat_detail_by_id"),
    ("friends-chat/<str:username>/recommend/", "recommend_friend_restaurant"),
    ("friends-chat/<str:username>/toggle-shared/", "toggle_shared_restaurant"),
    ("friends-chat/<str:username>/", "friends_chat_detail"),
    ("messages/", "message_inbox"),
    ("messages/restaurant/<int:restaurant_id>/", "message_restaurant"),
    ("messages/conversations/<int:conversation_id>/", "conversation_detail"),
    ("report/<str:content_type>/<int:content_id>/", "report_content"),
    ("nomz-admin/moderation/", "admin_moderation_dashboard"),
    ("nomz-admin/moderation/resolve/<int:report_id>/", "admin_resolve_report"),
]

for _route, _name in _SPA_NAMED:
    if _route == "":
        urlpatterns.append(
            path("", spa_shell_views.spa_index, name=_name),
        )
    elif "<" in _route:
        urlpatterns.append(
            path(_route, spa_shell_views.spa_index, name=_name),
        )
    else:
        urlpatterns.append(
            path(_route, spa_shell_views.spa_index, name=_name),
        )

# Catch-all: deep links and any path not listed above (still not under /api/)
# ✅ Proper catch-all for React SPA (must be LAST)
urlpatterns.append(
    re_path(r"^.*$", spa_shell_views.spa_index),
)
