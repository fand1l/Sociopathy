from django.urls import path
from .views import BookmarkListView, toggle_bookmark, remove_bookmark

app_name = "bookmarks"

urlpatterns = [
    path("bookmarks/", BookmarkListView.as_view(), name="list"),
    path("bookmark/<int:post_id>/", toggle_bookmark, name="toggle"),
    path("bookmark/<int:post_id>/remove/", remove_bookmark, name="remove"),
]
