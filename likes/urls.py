from django.urls import path
from .views import like_post

app_name = 'likes'

urlpatterns = [
    path('like/<int:post_id>/', like_post, name='like_post'),
]