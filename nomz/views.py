from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from nomz.ingestion.utils.score import compute_restaurant_composite_score
from nomz.scoring import refresh_restaurant_composite
from django.contrib.auth.models import User
from .forms import (
    ReviewResponseForm,
)
from .models import (
    Conversation,
    CompositeScoreAnomaly,
    Restaurant,
    Review,
    ReviewResponse,
    ModerationReport,
    SystemAuditLog,
    FriendMessage,
    FriendConversation,
    FriendSharedRestaurant,
)

NYC_MIN_LAT = 40.0
NYC_MAX_LAT = 41.5
NYC_MIN_LON = -75.5
NYC_MAX_LON = -72.0


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _refresh_restaurant_composite_fields(restaurant):
    return refresh_restaurant_composite(restaurant)


def _build_restaurant_score_insights(restaurant):
    current_score_data = compute_restaurant_composite_score(restaurant)
    composite_score_value = (
        _to_float(restaurant.composite_score)
        if restaurant.composite_score is not None
        else _to_float(current_score_data.get("composite_score"))
    )
    grade_score_value = (
        int(restaurant.grade_score_latest)
        if restaurant.grade_score_latest is not None
        else int(current_score_data.get("grade_score") or 0)
    )
    grade_value = (
        restaurant.grade_latest or current_score_data.get("grade") or ""
    ).strip()
    last_inspection_date_value = (
        restaurant.last_inspection_date
        or current_score_data.get("last_inspection_date")
    )

    score_summary = {
        "composite_score": composite_score_value,
        "grade": grade_value or "N/A",
        "grade_score": grade_score_value,
        "last_inspection_date": last_inspection_date_value,
        "review_count": int(current_score_data.get("review_count") or 0),
        "review_confidence": round(
            float(current_score_data.get("review_confidence") or 0.0) * 100, 1
        ),
    }

    review_factor_averages = current_score_data.get("review_factor_averages", {})
    review_factor_scores = current_score_data.get("review_factor_scores", {})
    review_factor_breakdown = [
        {
            "label": "Overall",
            "average_rating": review_factor_averages.get("overall_rating"),
            "score_100": review_factor_scores.get("overall_rating", 0),
        },
        {
            "label": "Food Quality",
            "average_rating": review_factor_averages.get("food_quality_rating"),
            "score_100": review_factor_scores.get("food_quality_rating", 0),
        },
        {
            "label": "Service Quality",
            "average_rating": review_factor_averages.get("service_quality_rating"),
            "score_100": review_factor_scores.get("service_quality_rating", 0),
        },
        {
            "label": "Ambience",
            "average_rating": review_factor_averages.get("ambience_rating"),
            "score_100": review_factor_scores.get("ambience_rating", 0),
        },
        {
            "label": "Location",
            "average_rating": review_factor_averages.get("location_rating"),
            "score_100": review_factor_scores.get("location_rating", 0),
        },
        {
            "label": "Value",
            "average_rating": review_factor_averages.get("value_rating"),
            "score_100": review_factor_scores.get("value_rating", 0),
        },
        {
            "label": "Dietary Accommodation",
            "average_rating": review_factor_averages.get(
                "dietary_accommodation_rating"
            ),
            "score_100": review_factor_scores.get("dietary_accommodation_rating", 0),
        },
        {
            "label": "Cleanliness",
            "average_rating": review_factor_averages.get("cleanliness_rating"),
            "score_100": review_factor_scores.get("cleanliness_rating", 0),
        },
    ]

    score_breakdown = current_score_data.get("score_breakdown", [])

    trend_rows = list(restaurant.inspections.order_by("-inspection_date", "-id")[:8])
    trend_rows.reverse()
    trend_points = []
    for inspection in trend_rows:
        point_score = compute_restaurant_composite_score(
            restaurant,
            as_of_date=inspection.inspection_date,
        )
        trend_points.append(
            {
                "date": inspection.inspection_date.isoformat(),
                "label": inspection.inspection_date.strftime("%b %d, %Y"),
                "composite_score": _to_float(point_score.get("composite_score")) or 0.0,
                "grade": (inspection.grade or "").strip().upper() or "N/A",
                "grade_score": int(point_score.get("grade_score") or 0),
                "critical_violations": int(inspection.critical_violations or 0),
                "noncritical_violations": int(inspection.noncritical_violations or 0),
                "inspection_type": inspection.inspection_type or "",
                "review_count": int(point_score.get("review_count") or 0),
            }
        )

    trend_summary = {
        "direction": "flat",
        "delta": 0.0,
        "has_data": bool(trend_points),
    }
    if len(trend_points) >= 2:
        delta = round(
            trend_points[-1]["composite_score"] - trend_points[0]["composite_score"], 2
        )
        trend_summary["delta"] = delta
        if delta > 1:
            trend_summary["direction"] = "up"
        elif delta < -1:
            trend_summary["direction"] = "down"

    location_scope = ""
    peers = Restaurant.objects.filter(is_active=True, composite_score__isnull=False)
    if restaurant.neighborhood:
        peers = peers.filter(neighborhood__iexact=restaurant.neighborhood)
        location_scope = restaurant.neighborhood
    elif restaurant.borough:
        peers = peers.filter(borough__iexact=restaurant.borough)
        location_scope = restaurant.borough
    elif restaurant.zip_code:
        peers = peers.filter(zip_code__startswith=(restaurant.zip_code or "")[:5])
        location_scope = (restaurant.zip_code or "")[:5]
    else:
        location_scope = "citywide"

    peer_rows = list(peers.values("id", "composite_score"))
    peer_count = len(peer_rows)
    neighborhood_comparison = {
        "location_scope": location_scope,
        "peer_count": peer_count,
        "rank": None,
        "percentile": None,
        "average_score": None,
        "delta_vs_average": None,
    }

    if composite_score_value is not None and peer_count > 0:
        sorted_rows = sorted(
            peer_rows,
            key=lambda item: float(item["composite_score"]),
            reverse=True,
        )
        restaurant_rank = next(
            (
                index + 1
                for index, item in enumerate(sorted_rows)
                if item["id"] == restaurant.id
            ),
            None,
        )
        if restaurant_rank is None:
            restaurant_rank = (
                sum(
                    1
                    for item in sorted_rows
                    if float(item["composite_score"]) > composite_score_value
                )
                + 1
            )

        average_score = round(
            sum(float(item["composite_score"]) for item in peer_rows) / peer_count,
            2,
        )
        percentile = round(((peer_count - restaurant_rank + 1) / peer_count) * 100, 1)
        neighborhood_comparison.update(
            {
                "rank": restaurant_rank,
                "percentile": percentile,
                "average_score": average_score,
                "delta_vs_average": round(composite_score_value - average_score, 2),
            }
        )

    return {
        "score_summary": score_summary,
        "score_breakdown": score_breakdown,
        "review_factor_breakdown": review_factor_breakdown,
        "trend_points": trend_points,
        "trend_summary": trend_summary,
        "neighborhood_comparison": neighborhood_comparison,
    }


def perform_dependency_health_checks() -> None:
    """
    Dependency checks for /health/.

    Kept as a function so tests can patch failure scenarios easily.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1;")
        cursor.fetchone()


def health_check(request):
    """
    Lightweight health endpoint for ELB/EB health checks.
    Must return HTTP 200 quickly and without auth redirects.
    """
    # Best-effort dependency checks. Keep it fast and avoid expensive ORM work.
    try:
        perform_dependency_health_checks()
        return JsonResponse({"status": "ok"}, status=200)
    except Exception as exc:
        # Let monitoring middleware convert non-200 responses into alerts/audit logs.
        return JsonResponse({"status": "degraded", "error": str(exc)[:200]}, status=503)


@staff_member_required
@require_POST
def admin_recalculate_scores(request):
    restaurant_id = (request.POST.get("restaurant_id") or "").strip()
    restaurant_name = (request.POST.get("restaurant_name") or "").strip()

    queryset = Restaurant.objects.all().order_by("id")
    if restaurant_id:
        try:
            queryset = queryset.filter(id=int(restaurant_id))
        except ValueError:
            messages.error(request, "Restaurant ID must be a number.")
            return redirect("dashboard")
    elif restaurant_name:
        exact_matches = queryset.filter(name__iexact=restaurant_name)
        exact_count = exact_matches.count()
        if exact_count == 1:
            queryset = exact_matches
        elif exact_count > 1:
            messages.error(
                request,
                "Multiple restaurants share that name. Please pick one from the dropdown.",
            )
            return redirect("dashboard")
        else:
            partial_matches = queryset.filter(name__icontains=restaurant_name)
            partial_count = partial_matches.count()
            if partial_count == 1:
                queryset = partial_matches
            elif partial_count > 1:
                messages.error(
                    request,
                    "Multiple restaurants match that name. Please pick one from the dropdown.",
                )
                return redirect("dashboard")
            else:
                messages.error(request, "No restaurant found with that name.")
                return redirect("dashboard")
    # If no id/name is provided, recompute for ALL restaurants by design.

    total = queryset.count()
    if total == 0:
        messages.info(request, "No restaurants matched the recalculation criteria.")
        return redirect("dashboard")

    updated = 0
    anomaly_count = 0
    for restaurant in queryset.iterator():
        score_data = refresh_restaurant_composite(
            restaurant,
            trigger_source="admin_dashboard",
            triggered_by=request.user,
            trigger_note="Admin dashboard trigger",
        )
        updated += 1
        anomaly_count += int(score_data.get("anomaly_count") or 0)

    SystemAuditLog.objects.create(
        actor_user=request.user,
        actor_username=request.user.username,
        level="INFO",
        action="admin_composite_score_recalculation",
        request_path=request.path,
        http_method=request.method,
        ip_address=request.META.get("REMOTE_ADDR"),
        metadata={
            "restaurant_id_filter": restaurant_id or None,
            "restaurant_name_filter": restaurant_name or None,
            "restaurants_updated": updated,
            "anomaly_flags_detected": anomaly_count,
        },
    )

    messages.success(
        request,
        (
            f"Recalculated scores for {updated}/{total} restaurant(s). "
            f"Detected {anomaly_count} anomaly flag(s)."
        ),
    )
    return redirect("dashboard")


@staff_member_required
@require_POST
def admin_resolve_score_anomaly(request, anomaly_id):
    anomaly = get_object_or_404(CompositeScoreAnomaly, id=anomaly_id)
    if not anomaly.is_resolved:
        anomaly.is_resolved = True
        anomaly.resolved_at = timezone.now()
        anomaly.resolved_by = request.user
        anomaly.save(update_fields=["is_resolved", "resolved_at", "resolved_by"])

        SystemAuditLog.objects.create(
            actor_user=request.user,
            actor_username=request.user.username,
            level="INFO",
            action="admin_score_anomaly_resolved",
            request_path=request.path,
            http_method=request.method,
            ip_address=request.META.get("REMOTE_ADDR"),
            metadata={
                "anomaly_id": anomaly.id,
                "restaurant_id": anomaly.restaurant_id,
                "anomaly_type": anomaly.anomaly_type,
            },
        )
        messages.success(request, f"Anomaly #{anomaly.id} marked as resolved.")
    else:
        messages.info(request, f"Anomaly #{anomaly.id} is already resolved.")
    return redirect("dashboard")


def is_restaurant_owner(user):
    """Helper function to check if user is a restaurant owner"""
    return hasattr(user, "userprofile") and user.userprofile.role == "restaurant"


@login_required(login_url="landing")
@require_http_methods(["POST"])
def user_logout(request):
    """
    User logout view
    Logs out the user and redirects to login page
    """
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("signin")


# ============================================================================
# RESTAURANT PROFILE MANAGEMENT VIEWS
# ============================================================================


# Add this to views.py


@login_required(login_url="landing")
@require_POST
def admin_toggle_user_status(request, user_id):
    """
    Directly toggle user active status from the admin dashboard.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden(
            "You do not have permission to perform this action."
        )

    user_to_change = get_object_or_404(User, id=user_id)
    action = request.POST.get("action")

    if user_to_change == request.user:
        messages.error(request, "You cannot change your own status!")
    elif user_to_change.is_superuser and not request.user.is_superuser:
        messages.error(
            request, "You do not have permission to change a superuser status."
        )
    else:
        if action == "activate":
            user_to_change.is_active = True
            messages.success(
                request, f"Access ALLOWED for user: {user_to_change.username}"
            )
        elif action == "deactivate":
            user_to_change.is_active = False
            messages.success(
                request, f"Access REVOKED for user: {user_to_change.username}"
            )
        else:
            messages.error(request, "Invalid action.")

        user_to_change.save()

    return redirect("dashboard")


# ============================================================================
# MODERATION & REVIEW VIEWS
# ============================================================================


@login_required(login_url="landing")
@require_POST
def respond_to_review(request, review_id):
    """
    Allow a restaurant owner to create or edit one public response per review.
    """
    review = get_object_or_404(
        Review.objects.select_related("restaurant", "restaurant__owner"),
        id=review_id,
    )
    restaurant = review.restaurant

    if restaurant.owner_id != request.user.id:
        return HttpResponseForbidden(
            "Only the owner of this restaurant can respond to this review."
        )

    if review.is_deleted:
        messages.error(
            request,
            "You cannot respond to a review that was removed by moderation.",
        )
        return redirect("profile")

    form = ReviewResponseForm(request.POST)
    if form.is_valid():
        response_text = form.cleaned_data["response_text"]
        review_response, created = ReviewResponse.objects.get_or_create(
            review=review,
            defaults={
                "restaurant": restaurant,
                "responder": request.user,
                "response_text": response_text,
            },
        )
        if not created:
            review_response.response_text = response_text
            review_response.restaurant = restaurant
            review_response.responder = request.user
            review_response.save(
                update_fields=[
                    "response_text",
                    "restaurant",
                    "responder",
                    "updated_at",
                ]
            )
            messages.success(request, "Your public response has been updated.")
        else:
            messages.success(request, "Your public response has been posted.")
    else:
        messages.error(
            request,
            "Could not save response. Please make sure the response text is valid.",
        )

    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("profile")


@staff_member_required
@require_POST
def admin_resolve_report(request, report_id):
    """
    Admins can take action on a report.
    """
    report = get_object_or_404(ModerationReport, id=report_id)
    action = request.POST.get("action")
    moderator_note = request.POST.get("moderator_note", "")

    if action == "dismiss":
        report.status = "DISMISSED"
        report.action_taken = "No action taken"
    elif action == "flag_fraud":
        if report.review:
            report.review.is_flagged = True
            report.review.save()
            report.action_taken = "Review flagged as fraudulent"
        elif report.reported_user:
            # Set flag on UserProfile
            if hasattr(report.reported_user, "userprofile"):
                report.reported_user.userprofile.is_flagged = True
                report.reported_user.userprofile.save()

            # Set flag on all Restaurants owned by this user
            Restaurant.objects.filter(owner=report.reported_user).update(
                is_flagged=True
            )

            report.action_taken = "User and associated restaurant(s) flagged for fraud"
        report.status = "RESOLVED"
    elif action == "unflag":
        if report.review:
            report.review.is_flagged = False
            report.review.save()
            report.action_taken = "Review un-flagged"
        elif report.reported_user:
            # Remove flag on UserProfile
            if hasattr(report.reported_user, "userprofile"):
                report.reported_user.userprofile.is_flagged = False
                report.reported_user.userprofile.save()

            # Remove flag on all Restaurants owned by this user
            Restaurant.objects.filter(owner=report.reported_user).update(
                is_flagged=False
            )

            report.action_taken = "User and associated restaurant(s) un-flagged"
        report.status = "PENDING"
    elif action == "delete":
        if report.review:
            report.review.is_deleted = True
            report.review.save()
            report.action_taken = "Review soft-deleted"
        report.status = "RESOLVED"
    elif action == "reevaluate":
        report.status = "PENDING"
        report.action_taken = "Moved back to pending for re-evaluation"

    report.moderator_note = moderator_note
    report.resolved_at = timezone.now()
    report.save()

    # Audit logging
    SystemAuditLog.objects.create(
        actor_user=request.user,
        actor_username=request.user.username,
        level="WARNING" if action != "dismiss" else "INFO",
        action=f"moderation_{action}",
        request_path=request.path,
        http_method=request.method,
        ip_address=request.META.get("REMOTE_ADDR"),
        metadata={
            "report_id": report.id,
            "action": action,
            "target": str(report),
        },
    )

    messages.success(request, f"Report {report_id} has been {report.status.lower()}.")
    return redirect("admin_moderation_dashboard")


@login_required(login_url="landing")
def message_restaurant(request, restaurant_id):
    if is_restaurant_owner(request.user):
        messages.error(
            request,
            "Restaurant owner accounts cannot start a diner-to-restaurant conversation.",
        )
        return redirect("restaurant_detail", restaurant_id=restaurant_id)

    restaurant = get_object_or_404(
        Restaurant.objects.select_related("owner"), id=restaurant_id
    )
    if not restaurant.owner_id:
        messages.error(
            request,
            "This restaurant does not yet have an owner account for messaging.",
        )
        return redirect("restaurant_detail", restaurant_id=restaurant_id)

    # Issue #62: respect the restaurant's messaging toggle
    if not restaurant.messaging_enabled:
        messages.error(
            request,
            f"{restaurant.name} has messaging disabled and is not accepting new messages at this time.",
        )
        return redirect("restaurant_detail", restaurant_id=restaurant_id)

    conversation, _ = Conversation.objects.get_or_create(
        restaurant=restaurant,
        diner=request.user,
    )
    return redirect("conversation_detail", conversation_id=conversation.id)


@login_required
def create_group_chat(request):
    """
    Creates a new group conversation.
    """
    if request.method == "POST":
        group_name = request.POST.get("group_name", "").strip()
        participant_ids = request.POST.getlist("participants")  # Multiple IDs

        if not group_name:
            messages.error(request, "Group name is required.")
            return redirect("friends_chat_index")

        conv = FriendConversation.objects.create(
            name=group_name, is_group=True, creator=request.user  # Set creator
        )
        conv.participants.add(request.user)  # Add self
        for p_id in participant_ids:
            try:
                user = User.objects.get(id=p_id)
                # Ensure only diners are added
                if hasattr(user, "userprofile") and user.userprofile.role == "diner":
                    conv.participants.add(user)
            except User.DoesNotExist:
                continue

        return redirect("friends_chat_detail_by_id", conversation_id=conv.id)

    return redirect("friends_chat_index")


@login_required
def manage_group_member(request, conversation_id):
    """
    Allows the group admin (creator) to add or remove members.
    """
    conv = get_object_or_404(FriendConversation, id=conversation_id, is_group=True)
    if conv.creator != request.user:
        messages.error(request, "Only the group creator can manage members.")
        return redirect("friends_chat_detail_by_id", conversation_id=conversation_id)

    if request.method == "POST":
        action = request.POST.get("action")
        username = request.POST.get("username", "").strip()
        user_id = request.POST.get("user_id")

        user = None
        if user_id:
            user = User.objects.filter(id=user_id).first()
        elif username:
            user = User.objects.filter(username=username).first()

        if user:
            if action == "add":
                # Ensure only diners are added
                if hasattr(user, "userprofile") and user.userprofile.role == "diner":
                    conv.participants.add(user)
                    messages.success(request, f"Added {user.username} to the group.")
                else:
                    messages.error(request, "Only diners can be added to chat groups.")
            elif action == "remove":
                if user == conv.creator:
                    messages.error(
                        request, "You cannot remove yourself from a group you created."
                    )
                else:
                    conv.participants.remove(user)
                    messages.success(
                        request, f"Removed {user.username} from the group."
                    )

    return redirect("friends_chat_detail_by_id", conversation_id=conversation_id)


@login_required
def leave_group(request, conversation_id):
    """
    Allows a member to leave a group.
    """
    conv = get_object_or_404(FriendConversation, id=conversation_id, is_group=True)
    if not conv.can_access(request.user):
        return redirect("friends_chat_index")

    if conv.creator == request.user:
        messages.error(
            request,
            "Creators cannot leave their own groups. Use 'Delete Group' (if available) or assign a new admin.",
        )
        return redirect("friends_chat_detail_by_id", conversation_id=conversation_id)

    conv.participants.remove(request.user)
    messages.success(request, f"You have left the group '{conv.name}'.")
    return redirect("friends_chat_index")


@login_required
def recommend_friend_restaurant(request, username=None, conversation_id=None):
    """
    Sends a restaurant recommendation to a chat or group.
    """
    if conversation_id:
        conversation = get_object_or_404(FriendConversation, id=conversation_id)
    else:
        target_user = get_object_or_404(User, username=username)
        user1, user2 = (
            (request.user, target_user)
            if request.user.id < target_user.id
            else (target_user, request.user)
        )
        conversation = get_object_or_404(
            FriendConversation, user1=user1, user2=user2, is_group=False
        )

    if request.method == "POST":
        restaurant_id = request.POST.get("restaurant_id")
        restaurant_name = request.POST.get("restaurant_name")
        body = request.POST.get("body", "")

        restaurant = None
        if restaurant_id:
            restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        elif restaurant_name:
            restaurant = Restaurant.objects.filter(name=restaurant_name).first()

        if restaurant:
            FriendMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                body=body,
                restaurant_recommendation=restaurant,
            )
            conversation.save()  # Update updated_at

    if conversation_id:
        return redirect("friends_chat_detail_by_id", conversation_id=conversation_id)
    return redirect("friends_chat_detail", username=username)


@login_required
def toggle_shared_restaurant(request, username=None, conversation_id=None):
    """
    Adds or removes a restaurant from the shared 'Together List' in a chat or group.
    """
    if conversation_id:
        conversation = get_object_or_404(FriendConversation, id=conversation_id)
    else:
        target_user = get_object_or_404(User, username=username)
        user1, user2 = (
            (request.user, target_user)
            if request.user.id < target_user.id
            else (target_user, request.user)
        )
        conversation = get_object_or_404(
            FriendConversation, user1=user1, user2=user2, is_group=False
        )

    if request.method == "POST":
        restaurant_id = request.POST.get("restaurant_id")
        restaurant_name = request.POST.get("restaurant_name")
        action = request.POST.get("action", "add")

        restaurant = None
        if restaurant_id:
            restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        elif restaurant_name:
            restaurant = Restaurant.objects.filter(name=restaurant_name).first()

        if restaurant:
            if action == "add":
                FriendSharedRestaurant.objects.get_or_create(
                    conversation=conversation,
                    restaurant=restaurant,
                    defaults={"added_by": request.user},
                )
            elif action == "remove":
                FriendSharedRestaurant.objects.filter(
                    conversation=conversation, restaurant=restaurant
                ).delete()

    if conversation_id:
        return redirect("friends_chat_detail_by_id", conversation_id=conversation_id)
    return redirect("friends_chat_detail", username=username)
