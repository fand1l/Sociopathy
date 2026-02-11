from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import ChatMessage, ChatThread

User = get_user_model()


class ChatThreadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="password123")
        self.other = User.objects.create_user(username="bob", password="password123")
        self.thread = ChatThread.objects.create()
        self.thread.participants.add(self.user, self.other)

    def test_other_participant(self):
        self.assertEqual(self.thread.other_participant(self.user), self.other)

    def test_message_create(self):
        message = ChatMessage.objects.create(
            thread=self.thread,
            sender=self.user,
            text="Hello",
        )
        self.assertEqual(message.thread, self.thread)
        self.assertEqual(message.sender, self.user)
        self.assertEqual(message.text, "Hello")
