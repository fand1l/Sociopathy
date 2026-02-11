from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ChatMessageForm
from .models import ChatThread

User = get_user_model()


@login_required
def thread_list(request):
    threads = (
        ChatThread.objects.filter(participants=request.user)
        .annotate(last_message_at=Max("messages__created_at"))
        .prefetch_related("participants")
        .order_by("-last_message_at", "-updated_at")
    )
    thread_items = [
        {"thread": thread, "other": thread.other_participant(request.user)}
        for thread in threads
    ]
    context = {
        "thread": None,
        "chat_messages": [],
        "other_user": None,
        "thread_items": thread_items,
        "form": ChatMessageForm(),
    }
    return render(request, "chat/chat_page.html", context)


@login_required
def chat_page(request, thread_id):
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    chat_messages = thread.messages.all().order_by("created_at")
    other_user = thread.participants.exclude(id=request.user.id).first()

    threads = (
        ChatThread.objects.filter(participants=request.user)
        .annotate(last_message_at=Max("messages__created_at"))
        .prefetch_related("participants")
        .order_by("-last_message_at", "-updated_at")
    )
    thread_items = [
        {"thread": item, "other": item.other_participant(request.user)}
        for item in threads
    ]

    context = {
        "thread": thread,
        "chat_messages": chat_messages,
        "other_user": other_user,
        "thread_items": thread_items,
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
