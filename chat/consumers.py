import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

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

        is_participant = await self.is_participant(user.id)
        if not is_participant:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = (data.get("message") or "").strip()

        if not message_text:
            return

        user = self.scope["user"]

        await self.save_message(user.id, message_text)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "sendMessage",
                "message": message_text,
                "username": user.username,
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

    async def sendMessage(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "username": event["username"],
                }
            )
        )
