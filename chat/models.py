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
