from django.shortcuts import render, redirect
from django.views.generic import ListView
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