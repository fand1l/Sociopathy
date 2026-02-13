import json

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from .models import ChatMessage, ChatThread

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        self.room_group_name = f"chat_{self.thread_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user = user

        is_participant = await self.is_participant(user.id)
        if not is_participant:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        online_count = await self.set_user_online(user.id, True)
        if online_count == 1:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "presence_update",
                    "user_id": user.id,
                    "is_online": True,
                },
            )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        if hasattr(self, "user"):
            online_count = await self.set_user_online(self.user.id, False)
            if online_count == 0:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "presence_update",
                        "user_id": self.user.id,
                        "is_online": False,
                    },
                )

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get("type", "message")

        if event_type == "typing":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_update",
                    "user_id": self.user.id,
                    "is_typing": bool(data.get("is_typing")),
                },
            )
            return

        if event_type == "read":
            message_id = data.get("message_id")
            if not message_id:
                return
            updated_ids = await self.mark_messages_read(self.user.id, message_id)
            if updated_ids:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "read_receipt",
                        "reader_id": self.user.id,
                        "message_ids": updated_ids,
                    },
                )
            return

        message_text = (data.get("message") or "").strip()
        if not message_text:
            return

        message = await self.save_message(self.user.id, message_text)
        if not message:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message.text,
                "username": self.user.username,
                "sender_id": self.user.id,
                "message_id": message.id,
                "created_at": message.created_at.isoformat(),
                "image_url": message.image.url if message.image else None,
                "file_url": message.file.url if message.file else None,
                "file_name": message.file.name.split("/")[-1] if message.file else None,
            },
        )

    @database_sync_to_async
    def is_participant(self, user_id):
        return ChatThread.objects.filter(
            id=self.thread_id,
            participants__id=user_id,
        ).exists()

    @database_sync_to_async
    def save_message(self, user_id, message_text):
        user = User.objects.get(id=user_id)
        thread = ChatThread.objects.get(id=self.thread_id)
        if not thread.participants.filter(id=user.id).exists():
            return None
        return ChatMessage.objects.create(sender=user, thread=thread, text=message_text)

    @database_sync_to_async
    def mark_messages_read(self, reader_id, message_id):
        thread = ChatThread.objects.get(id=self.thread_id)
        if not thread.participants.filter(id=reader_id).exists():
            return []
        reader = User.objects.get(id=reader_id)
        messages = (
            ChatMessage.objects.filter(thread=thread, id__lte=message_id)
            .exclude(sender_id=reader_id)
            .filter(read_at__isnull=True)
        )
        message_ids = list(messages.values_list("id", flat=True))
        if message_ids:
            messages.update(read_at=timezone.now(), read_by=reader)
        return message_ids

    @sync_to_async
    def set_user_online(self, user_id, is_online):
        key = f"chat_online_count_{user_id}"
        if is_online:
            try:
                return cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=300)
                return 1
        try:
            count = cache.decr(key)
        except ValueError:
            cache.delete(key)
            return 0
        if count <= 0:
            cache.delete(key)
            return 0
        return count

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message",
                    "message": event["message"],
                    "username": event["username"],
                    "sender_id": event["sender_id"],
                    "message_id": event["message_id"],
                    "created_at": event["created_at"],
                    "image_url": event.get("image_url"),
                    "file_url": event.get("file_url"),
                    "file_name": event.get("file_name"),
                }
            )
        )

    async def typing_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def presence_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "user_id": event["user_id"],
                    "is_online": event["is_online"],
                }
            )
        )

    async def read_receipt(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read_receipt",
                    "reader_id": event["reader_id"],
                    "message_ids": event["message_ids"],
                }
            )
        )
