from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from posts.models import Post
from .models import Bookmark


class BookmarkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester", password="pass12345"
        )
        self.other = get_user_model().objects.create_user(
            username="other", password="pass12345"
        )
        self.post = Post.objects.create(author=self.other, content="Hello")

    def test_toggle_bookmark(self):
        self.client.login(username="tester", password="pass12345")
        toggle_url = reverse("bookmarks:toggle", args=[self.post.id])

        self.client.post(toggle_url)
        self.assertTrue(
            Bookmark.objects.filter(user=self.user, post=self.post).exists()
        )

        self.client.post(toggle_url)
        self.assertFalse(
            Bookmark.objects.filter(user=self.user, post=self.post).exists()
        )

    def test_bookmark_list_requires_auth(self):
        response = self.client.get(reverse("bookmarks:list"))
        self.assertEqual(response.status_code, 302)

    def test_remove_bookmark(self):
        self.client.login(username="tester", password="pass12345")
        Bookmark.objects.create(user=self.user, post=self.post)

        remove_url = reverse("bookmarks:remove", args=[self.post.id])
        self.client.post(remove_url)

        self.assertFalse(
            Bookmark.objects.filter(user=self.user, post=self.post).exists()
        )
