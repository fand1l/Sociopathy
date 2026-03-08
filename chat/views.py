import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Max
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from relationships.models import Follow
from posts.models import Post
from .forms import (
    ChatGroupForm,
    ChatGroupMemberAddForm,
    ChatGroupMessageForm,
    ChatGroupRoleForm,
    ChatMessageForm,
)
from .models import (
    ChatGroup,
    ChatGroupMembership,
    ChatGroupMessage,
    ChatMessage,
    ChatReaction,
    ChatThread,
    ChatThreadNotificationSetting,
)

User = get_user_model()


def _display_username(user):
    username = getattr(user, "username", "")
    if not username:
        return ""
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return f"{username} ✅"
    return username


def _attach_shared_post_previews(messages):
    post_ids = {
        message.shared_post_id
        for message in messages
        if getattr(message, "shared_post_id", None)
    }
    if not post_ids:
        return

    posts_by_id = {
        post.id: post
        for post in Post.objects.filter(id__in=post_ids).select_related("reposted_post")
    }

    for message in messages:
        message.shared_post_image_url = ""
        post_id = getattr(message, "shared_post_id", None)
        if not post_id:
            continue

        post = posts_by_id.get(post_id)
        if not post:
            continue

        if post.reposted_post_id and post.reposted_post and post.reposted_post.image:
            message.shared_post_image_url = post.reposted_post.image.url
        elif post.image:
            message.shared_post_image_url = post.image.url


def _is_user_online(user_id):
    return bool(cache.get(f"chat_online_count_{user_id}"))


def _are_friends(profile_a, profile_b):
    if not profile_a or not profile_b:
        return False
    return (
        Follow.objects.filter(user_from=profile_a, user_to=profile_b).exists()
        and Follow.objects.filter(user_from=profile_b, user_to=profile_a).exists()
    )


def _is_thread_notifications_muted(thread, user):
    if not user or not user.is_authenticated:
        return False
    setting = ChatThreadNotificationSetting.objects.filter(
        thread=thread,
        user=user,
    ).only("is_muted").first()
    return bool(setting and setting.is_muted)


def _get_private_notification_recipient(thread, sender):
    recipient = thread.participants.exclude(id=sender.id).first()
    if not recipient:
        return None
    if _is_thread_notifications_muted(thread, recipient):
        return None
    return recipient


def _get_group_notification_recipients(group, sender):
    return User.objects.filter(
        chat_group_memberships__group=group,
        chat_group_memberships__is_banned=False,
        chat_group_memberships__is_muted_notifications=False,
    ).exclude(id=sender.id)


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
    chat_messages = list(thread.messages.all().order_by("created_at"))
    other_user = thread.participants.exclude(id=request.user.id).first()
    request_profile = getattr(request.user, "profile", None)
    other_profile = getattr(other_user, "profile", None) if other_user else None
    is_friend = _are_friends(request_profile, other_profile)
    is_online = bool(other_user) and is_friend and _is_user_online(other_user.id)

    reactions = (
        ChatReaction.objects.filter(message__thread=thread)
        .values("message_id", "emoji")
        .annotate(count=Count("id"))
    )
    user_reactions = (
        ChatReaction.objects.filter(message__thread=thread, user=request.user)
        .values("message_id", "emoji")
    )
    reaction_map = {}
    for item in reactions:
        reaction_map.setdefault(item["message_id"], []).append(item)
    user_reaction_map = {}
    for item in user_reactions:
        user_reaction_map.setdefault(item["message_id"], set()).add(item["emoji"])

    for message in chat_messages:
        message.reaction_summary = reaction_map.get(message.id, [])
        message.user_reactions = user_reaction_map.get(message.id, set())

    _attach_shared_post_previews(chat_messages)

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
        "thread_notifications_muted": _is_thread_notifications_muted(
            thread,
            request.user,
        ),
        "form": ChatMessageForm(),
    }
    return render(request, "chat/chat_page.html", context)


@login_required
@require_POST
def toggle_thread_notifications(request, thread_id):
    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}

    muted = bool(payload.get("muted"))
    setting, _ = ChatThreadNotificationSetting.objects.get_or_create(
        thread=thread,
        user=request.user,
    )
    setting.is_muted = muted
    setting.save(update_fields=["is_muted", "updated_at"])
    return JsonResponse({"status": "ok", "muted": setting.is_muted})


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
            "username": _display_username(request.user),
            "sender_id": request.user.id,
            "message_id": message.id,
            "created_at": message.created_at.isoformat(),
            "image_url": message.image.url if message.image else None,
            "file_url": message.file.url if message.file else None,
            "file_name": message.file.name.split("/")[-1] if message.file else None,
        },
    )

    recipient = _get_private_notification_recipient(thread, request.user)
    if recipient:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{recipient.id}",
            {
                "type": "notify_message",
                "scope": "thread",
                "thread_id": thread.id,
                "sender_id": request.user.id,
                "sender_username": _display_username(request.user),
                "message": message.text or "",
            },
        )

    return JsonResponse({"status": "ok", "message_id": message.id})


@login_required
def edit_message(request, thread_id, message_id):
    if request.method != "POST":
        return JsonResponse({"error": "Метод не підтримується."}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    message = get_object_or_404(ChatMessage, id=message_id, thread=thread)
    if message.sender_id != request.user.id:
        return JsonResponse({"error": "Недостатньо прав."}, status=403)
    if message.deleted_at:
        return JsonResponse({"error": "Повідомлення вже видалено."}, status=400)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}

    new_text = (payload.get("text") or "").strip()
    if not new_text and not (message.image or message.file):
        return JsonResponse({"error": "Повідомлення має містити текст або медіа."}, status=400)

    message.text = new_text
    message.edited_at = timezone.now()
    message.save(update_fields=["text", "edited_at"])

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{thread.id}",
        {
            "type": "message_edit",
            "message_id": message.id,
            "text": message.text,
            "edited_at": message.edited_at.isoformat(),
        },
    )

    return JsonResponse({"status": "ok", "text": message.text})


@login_required
def delete_message(request, thread_id, message_id):
    if request.method != "POST":
        return JsonResponse({"error": "Метод не підтримується."}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    message = get_object_or_404(ChatMessage, id=message_id, thread=thread)
    if message.sender_id != request.user.id:
        return JsonResponse({"error": "Недостатньо прав."}, status=403)
    if message.deleted_at:
        return JsonResponse({"error": "Повідомлення вже видалено."}, status=400)

    if message.image:
        message.image.delete(save=False)
        message.image = None
    if message.file:
        message.file.delete(save=False)
        message.file = None

    message.text = ""
    message.deleted_at = timezone.now()
    message.save(update_fields=["text", "deleted_at", "image", "file"])

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{thread.id}",
        {
            "type": "message_delete",
            "message_id": message.id,
            "deleted_at": message.deleted_at.isoformat(),
        },
    )

    return JsonResponse({"status": "ok"})


@login_required
def react_message(request, thread_id, message_id):
    if request.method != "POST":
        return JsonResponse({"error": "Метод не підтримується."}, status=405)

    thread = get_object_or_404(ChatThread, id=thread_id, participants=request.user)
    message = get_object_or_404(ChatMessage, id=message_id, thread=thread)
    if message.deleted_at:
        return JsonResponse({"error": "Повідомлення видалено."}, status=400)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}

    emoji = (payload.get("emoji") or "").strip()
    if not emoji:
        return JsonResponse({"error": "Не вказано реакцію."}, status=400)

    reaction = ChatReaction.objects.filter(
        message=message,
        user=request.user,
        emoji=emoji,
    ).first()
    if reaction:
        reaction.delete()
        action = "removed"
    else:
        ChatReaction.objects.create(message=message, user=request.user, emoji=emoji)
        action = "added"

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{thread.id}",
        {
            "type": "reaction_update",
            "message_id": message.id,
            "emoji": emoji,
            "action": action,
            "reactor_id": request.user.id,
        },
    )

    return JsonResponse({"status": "ok", "action": action})


class GroupListView(LoginRequiredMixin, ListView):
    model = ChatGroup
    template_name = "chat/group_list.html"
    context_object_name = "groups"

    def get_queryset(self):
        return (
            ChatGroup.objects.filter(
                memberships__user=self.request.user,
                memberships__is_banned=False,
            )
            .select_related("owner")
            .order_by("-updated_at")
        )


class GroupCreateView(LoginRequiredMixin, CreateView):
    model = ChatGroup
    form_class = ChatGroupForm
    template_name = "chat/group_create.html"

    def form_valid(self, form):
        group = form.save(commit=False)
        group.owner = self.request.user
        group.save()
        ChatGroupMembership.objects.create(
            group=group,
            user=self.request.user,
            role=ChatGroupMembership.Role.OWNER,
        )
        return redirect("chat:group_detail", group_id=group.id)


class GroupAccessMixin(LoginRequiredMixin):
    def get_group(self):
        if not hasattr(self, "group"):
            self.group = get_object_or_404(ChatGroup, id=self.kwargs["group_id"])
        return self.group

    def dispatch(self, request, *args, **kwargs):
        group = self.get_group()
        membership = group.get_membership(request.user)
        if not membership and group.is_owner(request.user):
            membership = ChatGroupMembership.objects.create(
                group=group,
                user=request.user,
                role=ChatGroupMembership.Role.OWNER,
            )
        if not membership or membership.is_banned:
            return HttpResponseForbidden("Недостатньо прав.")
        self.membership = membership
        return super().dispatch(request, *args, **kwargs)


class GroupDetailView(GroupAccessMixin, DetailView):
    model = ChatGroup
    pk_url_kwarg = "group_id"
    template_name = "chat/group_detail.html"
    context_object_name = "group"

    def get_queryset(self):
        return ChatGroup.objects.select_related("owner")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.get_object()
        group_messages = list(group.messages.select_related("sender"))
        _attach_shared_post_previews(group_messages)
        context["messages"] = group_messages
        context["message_form"] = ChatGroupMessageForm()
        context["member_add_form"] = ChatGroupMemberAddForm()
        context["role_form"] = ChatGroupRoleForm()
        context["membership"] = self.membership
        context["is_owner"] = group.is_owner(self.request.user)
        context["is_admin"] = group.is_admin(self.request.user)
        context["group_notifications_muted"] = bool(
            getattr(self.membership, "is_muted_notifications", False)
        )
        context["memberships"] = group.memberships.select_related("user").order_by(
            "-role", "user__username"
        )
        return context


class GroupNotificationMuteView(GroupAccessMixin, View):
    def post(self, request, group_id):
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            payload = {}

        muted = bool(payload.get("muted"))
        self.membership.is_muted_notifications = muted
        self.membership.save(update_fields=["is_muted_notifications"])
        return JsonResponse({"status": "ok", "muted": muted})


class GroupMessageCreateView(GroupAccessMixin, View):
    def post(self, request, group_id):
        form = ChatGroupMessageForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Повідомлення має містити текст.")
            return redirect("chat:group_detail", group_id=group_id)

        message = form.save(commit=False)
        message.group = self.get_group()
        message.sender = request.user
        message.save()
        self.group.save(update_fields=["updated_at"])

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{self.group.id}",
            {
                "type": "group_message",
                "message": message.text,
                "username": _display_username(request.user),
                "sender_id": request.user.id,
                "message_id": message.id,
                "created_at": message.created_at.isoformat(),
            },
        )

        for recipient in _get_group_notification_recipients(self.group, request.user):
            async_to_sync(channel_layer.group_send)(
                f"notifications_{recipient.id}",
                {
                    "type": "notify_message",
                    "scope": "group",
                    "group_id": self.group.id,
                    "group_name": self.group.name,
                    "sender_id": request.user.id,
                    "sender_username": _display_username(request.user),
                    "message": message.text,
                },
            )

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "ok", "message_id": message.id})
        return redirect("chat:group_detail", group_id=group_id)


class GroupMessageEditView(GroupAccessMixin, View):
    def post(self, request, group_id, message_id):
        group = self.get_group()
        message = get_object_or_404(ChatGroupMessage, id=message_id, group=group)
        if message.sender_id != request.user.id:
            return HttpResponseForbidden("Недостатньо прав.")
        if message.deleted_at:
            return JsonResponse({"error": "Повідомлення вже видалено."}, status=400)

        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            payload = {}

        new_text = (payload.get("text") or "").strip()
        if not new_text:
            return JsonResponse({"error": "Повідомлення має містити текст."}, status=400)

        message.text = new_text
        message.edited_at = timezone.now()
        message.save(update_fields=["text", "edited_at"])

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{group.id}",
            {
                "type": "group_message_edit",
                "message_id": message.id,
                "text": message.text,
                "edited_at": message.edited_at.isoformat(),
            },
        )

        return JsonResponse({"status": "ok", "text": message.text})


class GroupMessageDeleteView(GroupAccessMixin, View):
    def post(self, request, group_id, message_id):
        group = self.get_group()
        message = get_object_or_404(ChatGroupMessage, id=message_id, group=group)
        if not group.is_admin(request.user) and message.sender_id != request.user.id:
            return HttpResponseForbidden("Недостатньо прав.")
        if message.deleted_at:
            return JsonResponse({"error": "Повідомлення вже видалено."}, status=400)
        message.text = ""
        message.deleted_at = timezone.now()
        message.save(update_fields=["text", "deleted_at"])

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"group_{group.id}",
            {
                "type": "group_message_delete",
                "message_id": message.id,
                "deleted_at": message.deleted_at.isoformat(),
            },
        )

        return JsonResponse({"status": "ok"})


class GroupMemberAddView(GroupAccessMixin, View):
    def post(self, request, group_id):
        group = self.get_group()
        if not group.is_admin(request.user):
            return HttpResponseForbidden("Недостатньо прав.")
        form = ChatGroupMemberAddForm(request.POST)
        if not form.is_valid():
            return redirect("chat:group_detail", group_id=group.id)

        username = form.cleaned_data["username"].strip()
        if not username:
            messages.error(request, "Вкажіть нікнейм користувача.")
            return redirect("chat:group_detail", group_id=group.id)

        user = User.objects.filter(username=username).first()
        if not user:
            messages.error(request, "Користувача з таким нікнеймом не знайдено.")
            return redirect("chat:group_detail", group_id=group.id)
        membership, created = ChatGroupMembership.objects.get_or_create(
            group=group,
            user=user,
            defaults={"role": ChatGroupMembership.Role.MEMBER},
        )
        if not created:
            membership.role = ChatGroupMembership.Role.MEMBER
            membership.is_banned = False
            membership.banned_at = None
            membership.save(update_fields=["role", "is_banned", "banned_at"])

        return redirect("chat:group_detail", group_id=group.id)


class GroupMemberKickView(GroupAccessMixin, View):
    def post(self, request, group_id, user_id):
        group = self.get_group()
        if not group.is_admin(request.user):
            return HttpResponseForbidden("Недостатньо прав.")
        target = get_object_or_404(User, id=user_id)
        membership = get_object_or_404(ChatGroupMembership, group=group, user=target)
        if membership.role == ChatGroupMembership.Role.OWNER:
            return HttpResponseForbidden("Недостатньо прав.")
        if (
            membership.role == ChatGroupMembership.Role.ADMIN
            and not group.is_owner(request.user)
        ):
            return HttpResponseForbidden("Недостатньо прав.")
        membership.delete()
        return redirect("chat:group_detail", group_id=group.id)


class GroupMemberBanView(GroupAccessMixin, View):
    def post(self, request, group_id, user_id):
        group = self.get_group()
        if not group.is_admin(request.user):
            return HttpResponseForbidden("Недостатньо прав.")
        target = get_object_or_404(User, id=user_id)
        membership = get_object_or_404(ChatGroupMembership, group=group, user=target)
        if membership.role == ChatGroupMembership.Role.OWNER:
            return HttpResponseForbidden("Недостатньо прав.")
        if (
            membership.role == ChatGroupMembership.Role.ADMIN
            and not group.is_owner(request.user)
        ):
            return HttpResponseForbidden("Недостатньо прав.")
        membership.is_banned = True
        membership.banned_at = timezone.now()
        membership.save(update_fields=["is_banned", "banned_at"])
        return redirect("chat:group_detail", group_id=group.id)


class GroupMemberRoleUpdateView(GroupAccessMixin, View):
    def post(self, request, group_id, user_id):
        group = self.get_group()
        if not group.is_owner(request.user):
            return HttpResponseForbidden("Недостатньо прав.")
        form = ChatGroupRoleForm(request.POST)
        if not form.is_valid():
            return redirect("chat:group_detail", group_id=group.id)
        target = get_object_or_404(User, id=user_id)
        membership = get_object_or_404(ChatGroupMembership, group=group, user=target)
        if membership.role == ChatGroupMembership.Role.OWNER:
            return HttpResponseForbidden("Недостатньо прав.")
        membership.role = form.cleaned_data["role"]
        membership.save(update_fields=["role"])
        return redirect("chat:group_detail", group_id=group.id)
