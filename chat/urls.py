from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.thread_list, name="thread_list"),
    path("start/<str:username>/", views.start_private_chat, name="start_private_chat"),
    path("<int:thread_id>/", views.chat_page, name="chat_thread_detail"),
    path("<int:thread_id>/send/", views.send_message, name="chat_thread_send"),
]
