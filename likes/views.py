from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from posts.models import Post
from .models import Like

@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like_qs = Like.objects.filter(user=request.user, post=post)

    if like_qs.exists():
        like_qs.delete()
    else:
        Like.objects.create(user=request.user, post=post)

    return redirect(request.META.get('HTTP_REFERER', 'posts:home'))