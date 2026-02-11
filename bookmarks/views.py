from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView
from django.views.decorators.http import require_POST

from posts.models import Post
from likes.models import Like
from .models import Bookmark


class BookmarkListView(LoginRequiredMixin, ListView):
    model = Post
    template_name = "bookmarks/list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            Post.objects.filter(bookmarks__user=self.request.user)
            .select_related("author", "author__profile")
            .distinct()
        )

        queryset = queryset.annotate(
            is_liked=Exists(
                Like.objects.filter(user=self.request.user, post=OuterRef("pk"))
            ),
            is_bookmarked=Exists(
                Bookmark.objects.filter(user=self.request.user, post=OuterRef("pk"))
            ),
        )

        return queryset.order_by("-created_at")


@login_required
@require_POST
def toggle_bookmark(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    bookmark_qs = Bookmark.objects.filter(user=request.user, post=post)

    if bookmark_qs.exists():
        bookmark_qs.delete()
        bookmarked = False
    else:
        Bookmark.objects.create(user=request.user, post=post)
        bookmarked = True

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "bookmarked": bookmarked,
            }
        )

    return redirect(request.META.get("HTTP_REFERER", "bookmarks:list"))


@login_required
@require_POST
def remove_bookmark(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    Bookmark.objects.filter(user=request.user, post=post).delete()
    return redirect("bookmarks:list")
