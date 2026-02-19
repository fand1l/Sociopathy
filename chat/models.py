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
