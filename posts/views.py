from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from .models import Post
from likes.models import Like
from bookmarks.models import Bookmark
from django.db.models import Case, Exists, OuterRef, Value, When, IntegerField, F
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import UpdateView, DeleteView
from .forms import PostForm
from django.conf import settings
from accounts.models import Profile


def build_comment_tree(root_comments):
    if not root_comments:
        return []

    children_by_parent = {}
    pending_parent_ids = [comment.id for comment in root_comments]
    seen_ids = set(pending_parent_ids)

    while pending_parent_ids:
        batch = list(
            Post.objects.filter(parent_post_id__in=pending_parent_ids)
            .select_related("author", "author__profile")
            .order_by("created_at")
        )

        if not batch:
            break

        pending_parent_ids = []
        for comment in batch:
            if comment.id in seen_ids:
                continue
            seen_ids.add(comment.id)
            children_by_parent.setdefault(comment.parent_post_id, []).append(comment)
            pending_parent_ids.append(comment.id)

    def build(comment):
        return {
            "comment": comment,
            "children": [build(child) for child in children_by_parent.get(comment.id, [])],
        }

    return [build(comment) for comment in root_comments]

class FeedView(ListView):
    model = Post
    template_name = "posts/feed.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        queryset = Post.objects.all()
        queryset = queryset.select_related("author", "author__profile")

        if self.request.user.is_authenticated:
            profile, _ = Profile.objects.get_or_create(user=self.request.user)
            friends_profiles = profile.following.filter(followers=profile)
            following_profiles = profile.following.exclude(pk__in=friends_profiles)

            friend_user_ids = friends_profiles.values_list("user_id", flat=True)
            following_user_ids = following_profiles.values_list("user_id", flat=True)

            queryset = queryset.annotate(
                is_liked=Exists(
                    Like.objects.filter(user=self.request.user, post=OuterRef('pk'))
                ),
                is_bookmarked=Exists(
                    Bookmark.objects.filter(
                        user=self.request.user,
                        post=OuterRef('pk')
                    )
                ),
                feed_bucket=Case(
                    When(author_id__in=friend_user_ids, then=Value(0)),
                    When(author_id__in=following_user_ids, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
                feed_secondary=Case(
                    When(author_id__in=friend_user_ids, then=Value(0.0)),
                    When(author_id__in=following_user_ids, then=Value(0.0)),
                    default=F("recommendation_score"),
                ),
            )

            return queryset.order_by('feed_bucket', '-feed_secondary', '-created_at')

        return queryset.order_by('-recommendation_score', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('form', PostForm())
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('posts:home')

        self.object_list = self.get_queryset()
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)
    
class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'posts/post_form.html'
    success_url = reverse_lazy('posts:home')

    def test_func(self):
        return self.request.user == self.get_object().author

class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = 'posts/post_confirm_delete.html'
    success_url = reverse_lazy('posts:home')

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author


def post_detail(request, pk):
    post_queryset = Post.objects.select_related("author", "author__profile")
    if request.user.is_authenticated:
        post_queryset = post_queryset.annotate(
            is_liked=Exists(
                Like.objects.filter(user=request.user, post=OuterRef("pk"))
            ),
            is_bookmarked=Exists(
                Bookmark.objects.filter(user=request.user, post=OuterRef("pk"))
            ),
        )

    post = get_object_or_404(post_queryset, pk=pk)
    if not request.user.is_authenticated:
        post.is_liked = False
        post.is_bookmarked = False

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.author = request.user
            comment.parent_post = post
            comment.save()
            return redirect("posts:post_detail", pk=post.pk)
    else:
        form = PostForm()

    top_level_comments = (
        Post.objects.filter(parent_post=post)
        .select_related("author", "author__profile")
        .order_by("created_at")
    )

    paginator = Paginator(top_level_comments, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    comment_tree = build_comment_tree(list(page_obj.object_list))

    return render(
        request,
        "posts/post_detail.html",
        {
            "post": post,
            "comment_tree": comment_tree,
            "form": form,
            "page_obj": page_obj,
        },
    )