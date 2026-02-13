from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from relationships.models import Follow
from .forms import ChatMessageForm
from .models import ChatThread

User = get_user_model()


def _is_user_online(user_id):
    return bool(cache.get(f"chat_online_count_{user_id}"))


def _are_friends(profile_a, profile_b):
    if not profile_a or not profile_b:
        return False
    return (
        Follow.objects.filter(user_from=profile_a, user_to=profile_b).exists()
        and Follow.objects.filter(user_from=profile_b, user_to=profile_a).exists()
    )


@login_required
def thread_list(request):
    threads = (
        ChatThread.objects.filter(participants=request.user)
        .annotate(last_message_at=Max("messages__created_at"))
        .prefetch_related("participants")
        .order_by("-last_message_at", "-updated_at")
    )
    request_profile = getattr(request.user, "profile", None)
    thread_items = []
    for thread in threads:
        other_user = thread.other_participant(request.user)
        other_profile = getattr(other_user, "profile", None) if other_user else None
        is_friend = _are_friends(request_profile, other_profile)
        thread_items.append(
            {
                "thread": thread,
                "other": other_user,
                "is_friend": is_friend,
                "is_online": is_friend and other_user and _is_user_online(other_user.id),
            }
        )
    context = {
        "thread": None,
        "chat_messages": [],
        "other_user": None,
        "thread_items": thread_items,
        "is_friend": False,
        "is_online": False,
        "form": ChatMessageForm(),
    }
    return render(request, "chat/chat_page.html", context)


@login_required
def chat_page(request, thread_id):
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    chat_messages = thread.messages.all().order_by("created_at")
    other_user = thread.participants.exclude(id=request.user.id).first()
    request_profile = getattr(request.user, "profile", None)
    other_profile = getattr(other_user, "profile", None) if other_user else None
    is_friend = _are_friends(request_profile, other_profile)
    is_online = bool(other_user) and is_friend and _is_user_online(other_user.id)

    threads = (
        ChatThread.objects.filter(participants=request.user)
        .annotate(last_message_at=Max("messages__created_at"))
        .prefetch_related("participants")
        .order_by("-last_message_at", "-updated_at")
    )
    thread_items = []
    for item in threads:
        item_other_user = item.other_participant(request.user)
        item_other_profile = (
            getattr(item_other_user, "profile", None) if item_other_user else None
        )
        item_is_friend = _are_friends(request_profile, item_other_profile)
        thread_items.append(
            {
                "thread": item,
                "other": item_other_user,
                "is_friend": item_is_friend,
                "is_online": item_is_friend
                and item_other_user
                and _is_user_online(item_other_user.id),
            }
        )

    context = {
        "thread": thread,
        "chat_messages": chat_messages,
        "other_user": other_user,
        "thread_items": thread_items,
        "is_friend": is_friend,
        "is_online": is_online,
        "form": ChatMessageForm(),
    }
    return render(request, "chat/chat_page.html", context)


@login_required
def start_private_chat(request, username):
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        messages.info(request, "Ви не можете написати самому собі.")
        return redirect("accounts:profile")

    thread = (
        ChatThread.objects.filter(participants=request.user)
        .filter(participants=other_user)
        .distinct()
        .first()
    )

    if not thread:
        thread = ChatThread.objects.create()
        thread.participants.add(request.user, other_user)

    return redirect("chat:chat_thread_detail", thread_id=thread.id)


@login_required
def send_message(request, thread_id):
    if request.method != "POST":
        return JsonResponse({"error": "Метод не підтримується."}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    form = ChatMessageForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": form.errors.get("__all__", form.errors)}, status=400)

    message = form.save(commit=False)
    message.thread = thread
    message.sender = request.user
    message.save()
    thread.save(update_fields=["updated_at"])

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{thread.id}",
        {
            "type": "chat_message",
            "message": message.text or "",
            "username": request.user.username,
            "sender_id": request.user.id,
            "message_id": message.id,
            "created_at": message.created_at.isoformat(),
            "image_url": message.image.url if message.image else None,
            "file_url": message.file.url if message.file else None,
            "file_name": message.file.name.split("/")[-1] if message.file else None,
        },
    )

    return JsonResponse({"status": "ok", "message_id": message.id})
