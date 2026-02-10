from django.shortcuts import render
from django.views.generic import ListView
from django.urls import reverse_lazy
from .models import Post
from likes.models import Like
from django.db.models import Exists, OuterRef
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import UpdateView, DeleteView
from .forms import PostForm

class PostListView(ListView):
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
        context['form'] = PostForm() 
        return context
    
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