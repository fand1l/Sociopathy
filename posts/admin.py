from django.contrib import admin

from .models import Post, PostImage

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('author', 'created_at')
    list_filter = ('created_at',)


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ('post', 'created_at')
    list_filter = ('created_at',)