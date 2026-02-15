from django.urls import path
from .views import FeedView, PostUpdateView, PostDeleteView, post_detail
from django.conf import settings
from django.conf.urls.static import static

app_name = "posts"

urlpatterns = [
    path("", FeedView.as_view(), name="home"),
    path("post/<int:pk>/", post_detail, name="post_detail"),
    path("post/<int:pk>/edit/", PostUpdateView.as_view(), name="post_update"),
    path("post/<int:pk>/delete/", PostDeleteView.as_view(), name="post_delete"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)