from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.thread_list, name="thread_list"),
    path("groups/", views.GroupListView.as_view(), name="group_list"),
    path("groups/create/", views.GroupCreateView.as_view(), name="group_create"),
    path("groups/<int:group_id>/", views.GroupDetailView.as_view(), name="group_detail"),
    path(
        "groups/<int:group_id>/mute-notifications/",
        views.GroupNotificationMuteView.as_view(),
        name="group_mute_notifications",
    ),
    path(
        "groups/<int:group_id>/send/",
        views.GroupMessageCreateView.as_view(),
        name="group_message_send",
    ),
    path(
        "groups/<int:group_id>/message/<int:message_id>/delete/",
        views.GroupMessageDeleteView.as_view(),
        name="group_message_delete",
    ),
    path(
        "groups/<int:group_id>/message/<int:message_id>/edit/",
        views.GroupMessageEditView.as_view(),
        name="group_message_edit",
    ),
    path(
        "groups/<int:group_id>/members/add/",
        views.GroupMemberAddView.as_view(),
        name="group_member_add",
    ),
    path(
        "groups/<int:group_id>/members/<int:user_id>/kick/",
        views.GroupMemberKickView.as_view(),
        name="group_member_kick",
    ),
    path(
        "groups/<int:group_id>/members/<int:user_id>/ban/",
        views.GroupMemberBanView.as_view(),
        name="group_member_ban",
    ),
    path(
        "groups/<int:group_id>/members/<int:user_id>/role/",
        views.GroupMemberRoleUpdateView.as_view(),
        name="group_member_role",
    ),
    path("start/<str:username>/", views.start_private_chat, name="start_private_chat"),
    path("<int:thread_id>/", views.chat_page, name="chat_thread_detail"),
    path(
        "<int:thread_id>/mute-notifications/",
        views.toggle_thread_notifications,
        name="chat_thread_mute_notifications",
    ),
    path("<int:thread_id>/send/", views.send_message, name="chat_thread_send"),
    path(
        "<int:thread_id>/message/<int:message_id>/edit/",
        views.edit_message,
        name="chat_message_edit",
    ),
    path(
        "<int:thread_id>/message/<int:message_id>/delete/",
        views.delete_message,
        name="chat_message_delete",
    ),
    path(
        "<int:thread_id>/message/<int:message_id>/react/",
        views.react_message,
        name="chat_message_react",
    ),
]
