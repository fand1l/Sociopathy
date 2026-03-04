from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from .models import Post
from likes.models import Like
from bookmarks.models import Bookmark
from django.db.models import Case, Exists, OuterRef, Value, When, IntegerField, F, Q, Max
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.generic import UpdateView, DeleteView
from .forms import PostForm
from django.conf import settings
from accounts.models import Profile
from django.contrib.auth import get_user_model
from django.db import connection
from django.contrib import messages

from chat.models import ChatGroup, ChatGroupMembership, ChatGroupMessage, ChatMessage, ChatThread


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
        queryset = queryset.select_related(
            "author",
            "author__profile",
            "reposted_post",
            "reposted_post__author",
            "reposted_post__author__profile",
        )

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
        if self.request.user.is_authenticated:
            context["share_recipients"] = _get_share_recipients(self.request.user)
            context["share_groups"] = _get_share_groups(self.request.user)
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
    post_queryset = Post.objects.select_related(
        "author",
        "author__profile",
        "reposted_post",
        "reposted_post__author",
        "reposted_post__author__profile",
    )
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
            "share_recipients": _get_share_recipients(request.user)
            if request.user.is_authenticated
            else [],
            "share_groups": _get_share_groups(request.user)
            if request.user.is_authenticated
            else [],
        },
    )


@login_required
@require_POST
def repost_post(request, pk):
    original_post = get_object_or_404(
        Post.objects.select_related("author", "author__profile"),
        pk=pk,
    )

    if original_post.parent_post_id:
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        return redirect(next_url or "posts:home")

    if original_post.reposted_post_id:
        original_post = original_post.reposted_post

    Post.objects.create(
        author=request.user,
        content=original_post.content,
        image=original_post.image,
        reposted_post=original_post,
    )

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    return redirect(next_url or "posts:home")


User = get_user_model()


def _build_share_text(post):
    post_url = reverse_lazy("posts:post_detail", kwargs={"pk": post.pk})
    content_preview = (post.content or "").strip()
    if len(content_preview) > 180:
        content_preview = f"{content_preview[:177]}..."
    if content_preview:
        return f"Поділився постом:\n{content_preview}\n{post_url}"
    return f"Поділився постом:\n{post_url}"


def _parse_selected_user_ids(request):
    raw_ids = request.POST.get("selected_user_ids", "")
    ids = []
    for value in raw_ids.split(","):
        value = value.strip()
        if value.isdigit():
            ids.append(int(value))

    unique_ids = []
    seen = set()
    for user_id in ids:
        if user_id not in seen:
            seen.add(user_id)
            unique_ids.append(user_id)
    return unique_ids


def _parse_selected_group_ids(request):
    raw_ids = request.POST.get("selected_group_ids", "")
    ids = []
    for value in raw_ids.split(","):
        value = value.strip()
        if value.isdigit():
            ids.append(int(value))

    unique_ids = []
    seen = set()
    for group_id in ids:
        if group_id not in seen:
            seen.add(group_id)
            unique_ids.append(group_id)
    return unique_ids


def _get_share_recipients(user):
    users = list(
        User.objects.exclude(id=user.id)
        .select_related("profile")
        .order_by("username")
    )
    threads = (
        ChatThread.objects.filter(participants=user)
        .annotate(last_message_at=Max("messages__created_at"))
        .prefetch_related("participants")
        .order_by("-last_message_at", "-updated_at")
    )

    last_message_map = {}
    for thread in threads:
        other_user = thread.other_participant(user)
        if not other_user:
            continue
        current_timestamp = last_message_map.get(other_user.id)
        if not current_timestamp or (
            thread.last_message_at and thread.last_message_at > current_timestamp
        ):
            last_message_map[other_user.id] = thread.last_message_at

    users.sort(
        key=lambda item: (
            last_message_map.get(item.id) is None,
            -last_message_map[item.id].timestamp()
            if last_message_map.get(item.id)
            else 0,
            item.username.lower(),
        )
    )
    return users


def _get_share_groups(user):
    return list(
        ChatGroup.objects.filter(
            memberships__user=user,
            memberships__is_banned=False,
        )
        .distinct()
        .order_by("-updated_at")
    )


@login_required
@require_POST
def share_post_create_group(request, pk):
    post = get_object_or_404(Post, pk=pk)
    selected_user_ids = _parse_selected_user_ids(request)
    selected_group_ids = _parse_selected_group_ids(request)
    if selected_group_ids:
        messages.error(request, "Для створення нової групи вибирайте тільки користувачів.")
        return redirect(request.POST.get("next") or "posts:home")

    if len(selected_user_ids) < 2:
        messages.error(request, "Виберіть щонайменше двох користувачів для створення групи.")
        return redirect(request.POST.get("next") or "posts:home")

    recipients = list(
        User.objects.filter(id__in=selected_user_ids).exclude(id=request.user.id)
    )
    if len(recipients) < 2:
        messages.error(request, "Не вдалося знайти обраних користувачів.")
        return redirect(request.POST.get("next") or "posts:home")

    group = ChatGroup.objects.create(
        name=f"Пост від {request.user.username}",
        owner=request.user,
    )
    ChatGroupMembership.objects.create(
        group=group,
        user=request.user,
        role=ChatGroupMembership.Role.OWNER,
    )
    ChatGroupMembership.objects.bulk_create(
        [
            ChatGroupMembership(
                group=group,
                user=recipient,
                role=ChatGroupMembership.Role.MEMBER,
            )
            for recipient in recipients
        ]
    )

    ChatGroupMessage.objects.create(
        group=group,
        sender=request.user,
        text=_build_share_text(post),
    )
    group.save(update_fields=["updated_at"])
    messages.success(request, "Групу створено, пост надіслано.")
    return redirect("chat:group_detail", group_id=group.id)


@login_required
@require_POST
def share_post_separately(request, pk):
    post = get_object_or_404(Post, pk=pk)
    selected_user_ids = _parse_selected_user_ids(request)
    selected_group_ids = _parse_selected_group_ids(request)
    if not selected_user_ids and not selected_group_ids:
        messages.error(request, "Виберіть хоча б одного користувача або групу.")
        return redirect(request.POST.get("next") or "posts:home")

    recipients = list(
        User.objects.filter(id__in=selected_user_ids).exclude(id=request.user.id)
    )
    groups = list(
        ChatGroup.objects.filter(
            id__in=selected_group_ids,
            memberships__user=request.user,
            memberships__is_banned=False,
        ).distinct()
    )
    if not recipients and not groups:
        messages.error(request, "Не вдалося знайти обраних користувачів або групи.")
        return redirect(request.POST.get("next") or "posts:home")

    share_text = _build_share_text(post)
    for recipient in recipients:
        thread = (
            ChatThread.objects.filter(participants=request.user)
            .filter(participants=recipient)
            .distinct()
            .first()
        )
        if not thread:
            thread = ChatThread.objects.create()
            thread.participants.add(request.user, recipient)

        ChatMessage.objects.create(
            thread=thread,
            sender=request.user,
            text=share_text,
        )
        thread.save(update_fields=["updated_at"])

    for group in groups:
        ChatGroupMessage.objects.create(
            group=group,
            sender=request.user,
            text=share_text,
        )
        group.save(update_fields=["updated_at"])

    messages.success(request, "Пост надіслано у вибрані чати та групи.")
    return redirect(request.POST.get("next") or "posts:home")


def search_view(request):
    raw_query = (request.GET.get("q") or "").strip()
    query = raw_query[1:] if raw_query.startswith("@") else raw_query
    display_query = raw_query
    user_results = []
    post_results = []
    user_count = 0
    post_count = 0

    if query:
        use_python_search = (
            connection.vendor == "sqlite"
            and any(ord(char) > 127 for char in query)
        )

        if use_python_search:
            query_folded = query.casefold()
            users_qs = User.objects.select_related("profile").order_by("username")
            filtered_users = [
                user
                for user in users_qs
                if query_folded in (user.username or "").casefold()
                or query_folded in (user.profile.bio or "").casefold()
            ]
            user_count = len(filtered_users)
            user_results = filtered_users[:12]

            posts_qs = (
                Post.objects.filter(parent_post__isnull=True)
                .select_related(
                    "author",
                    "author__profile",
                    "reposted_post",
                    "reposted_post__author",
                    "reposted_post__author__profile",
                )
                .order_by("-created_at")
            )
            filtered_posts = []
            for post in posts_qs:
                content = (post.content or "").casefold()
                reposted_content = ""
                if post.reposted_post_id:
                    reposted_content = (post.reposted_post.content or "").casefold()
                author_name = (post.author.username or "").casefold()
                if (
                    query_folded in content
                    or query_folded in reposted_content
                    or query_folded in author_name
                ):
                    filtered_posts.append(post)
            post_count = len(filtered_posts)
            post_results = filtered_posts[:20]
        else:
            users_qs = (
                User.objects.select_related("profile")
                .filter(
                    Q(username__icontains=query)
                    | Q(profile__bio__icontains=query)
                )
                .order_by("username")
            )
            user_count = users_qs.count()
            user_results = users_qs[:12]

            posts_qs = (
                Post.objects.filter(parent_post__isnull=True)
                .select_related(
                    "author",
                    "author__profile",
                    "reposted_post",
                    "reposted_post__author",
                    "reposted_post__author__profile",
                )
                .filter(
                    Q(content__icontains=query)
                    | Q(author__username__icontains=query)
                    | Q(reposted_post__content__icontains=query)
                )
                .distinct()
                .order_by("-created_at")
            )
            post_count = posts_qs.count()
            post_results = posts_qs[:20]

    return render(
        request,
        "posts/search.html",
        {
            "query": query,
            "display_query": display_query,
            "user_results": user_results,
            "post_results": post_results,
            "user_count": user_count,
            "post_count": post_count,
        },
    )