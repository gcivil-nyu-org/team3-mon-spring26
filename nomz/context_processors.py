from django.db.models import Q
from .models import Message, FriendMessage


def unread_counts(request):
    """
    Returns unread counts for both restaurant messages and friend chats.
    """
    if not request.user.is_authenticated:
        return {
            "unread_messages_count": 0,
            "unread_friends_count": 0,
        }

    # Restaurant messages
    unread_messages = (
        Message.objects.filter(
            Q(conversation__diner=request.user)
            | Q(conversation__restaurant__owner=request.user),
            is_read=False,
        )
        .exclude(sender=request.user)
        .distinct()
        .count()
    )

    # Friend chats
    unread_friends = (
        FriendMessage.objects.filter(
            conversation__participants=request.user, is_read=False
        )
        .exclude(sender=request.user)
        .distinct()
        .count()
    )

    return {
        "unread_messages_count": unread_messages,
        "unread_friends_count": unread_friends,
    }


def unread_messages_count(request):
    """Standalone context processor returning only the restaurant-message unread count."""
    if not request.user.is_authenticated:
        return {"unread_messages_count": 0}

    count = (
        Message.objects.filter(
            Q(conversation__diner=request.user)
            | Q(conversation__restaurant__owner=request.user),
            is_read=False,
        )
        .exclude(sender=request.user)
        .distinct()
        .count()
    )
    return {"unread_messages_count": count}
