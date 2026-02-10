from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.urls import reverse_lazy
from .models import Post
from likes.models import Like
from django.db.models import Exists, OuterRef
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import UpdateView, DeleteView
from .forms import PostForm
from django.conf import settings

class FeedView(ListView):
    model = Post
    template_name = "posts/feed.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        queryset = Post.objects.all()
        queryset = queryset.select_related("author", "author__profile")

        if self.request.user.is_authenticated:
            queryset = queryset.annotate(
                is_liked=Exists(
                    Like.objects.filter(user=self.request.user, post=OuterRef('pk'))
                )
            )

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