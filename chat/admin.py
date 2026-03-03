from django.contrib import admin

from .models import (
    ChatGroup,
    ChatGroupMembership,
    ChatGroupMessage,
    ChatMessage,
    ChatThread,
)


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "updated_at")
    search_fields = ("participants__username",)
    filter_horizontal = ("participants",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")
    search_fields = ("sender__username", "text")
    list_filter = ("created_at",)


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "created_at")
    search_fields = ("name", "owner__username")


@admin.register(ChatGroupMembership)
class ChatGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role", "is_banned", "joined_at")
    list_filter = ("role", "is_banned")
    search_fields = ("group__name", "user__username")


@admin.register(ChatGroupMessage)
class ChatGroupMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "group", "sender", "created_at", "deleted_at")
    list_filter = ("created_at", "deleted_at")
    search_fields = ("group__name", "sender__username", "text")
