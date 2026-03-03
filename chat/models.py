from django.conf import settings
from django.db import models


class ChatThread(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="chat_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def other_participant(self, user):
        return self.participants.exclude(id=user.id).first()

    def __str__(self):
        participants = list(self.participants.values_list("username", flat=True))
        return f"ChatThread {self.id} ({', '.join(participants)})"


class ChatGroup(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_chat_groups",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ChatGroupMembership",
        related_name="chat_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (#{self.id})"

    def get_membership(self, user):
        if not user or not user.is_authenticated:
            return None
        return self.memberships.filter(user=user).first()

    def is_owner(self, user):
        return bool(user and user.is_authenticated and self.owner_id == user.id)

    def is_admin(self, user):
        membership = self.get_membership(user)
        if not membership or membership.is_banned:
            return False
        return membership.role in {
            ChatGroupMembership.Role.ADMIN,
            ChatGroupMembership.Role.OWNER,
        }

    def is_member(self, user):
        membership = self.get_membership(user)
        return bool(membership and not membership.is_banned)


class ChatGroupMembership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member", "Учасник"
        ADMIN = "admin", "Адмін"
        OWNER = "owner", "Власник"

    group = models.ForeignKey(
        ChatGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_group_memberships",
    )
    role = models.CharField(
        max_length=12,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    is_banned = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    banned_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_chat_group_member",
            )
        ]

    def __str__(self):
        return f"{self.user_id} in {self.group_id} ({self.role})"


class ChatGroupMessage(models.Model):
    group = models.ForeignKey(
        ChatGroup,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_group_messages",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        preview = self.text.strip()
        return preview[:50] + ("..." if len(preview) > 50 else "")


class ChatMessage(models.Model):
    thread = models.ForeignKey(
        ChatThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    text = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="chat_images",
        blank=True,
        null=True,
    )
    file = models.FileField(
        upload_to="chat_files",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    read_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="read_messages",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        if self.text:
            preview = self.text.strip()
            return preview[:50] + ("..." if len(preview) > 50 else "")
        if self.image:
            return "Image message"
        if self.file:
            return f"File: {self.file.name.split('/')[-1]}"
        return "Message"


class ChatReaction(models.Model):
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_reactions",
    )
    emoji = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user", "emoji"],
                name="unique_chat_reaction",
            )
        ]

    def __str__(self):
        return f"{self.user_id}:{self.emoji} on {self.message_id}"
