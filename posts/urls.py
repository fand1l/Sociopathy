from django.urls import path
from .views import (
    FeedView,
    PostUpdateView,
    PostDeleteView,
    post_detail,
    summarize_post,
    repost_post,
    search_view,
    share_post_create_group,
    share_post_separately,
)
from django.conf import settings
from django.conf.urls.static import static

app_name = "posts"

urlpatterns = [
    path("", FeedView.as_view(), name="home"),
    path("search/", search_view, name="search"),
    path("post/<int:pk>/", post_detail, name="post_detail"),
    path("post/<int:pk>/summary/", summarize_post, name="post_summary"),
    path("post/<int:pk>/repost/", repost_post, name="post_repost"),
    path("post/<int:pk>/share/group/", share_post_create_group, name="post_share_group"),
    path("post/<int:pk>/share/separate/", share_post_separately, name="post_share_separate"),
    path("post/<int:pk>/edit/", PostUpdateView.as_view(), name="post_update"),
    path("post/<int:pk>/delete/", PostDeleteView.as_view(), name="post_delete"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)