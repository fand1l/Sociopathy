from django.urls import re_path

from .consumers import ChatConsumer, ChatGroupConsumer, NotificationConsumer

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
    re_path(r"ws/chat/(?P<thread_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"ws/chat/group/(?P<group_id>\d+)/$", ChatGroupConsumer.as_asgi()),
]
