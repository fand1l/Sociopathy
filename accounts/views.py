import json

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Exists, OuterRef
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import RegisterForm, ProfileForm
from .models import Profile
from likes.models import Like
from bookmarks.models import Bookmark
from posts.models import Post

User = get_user_model()


def get_profile_posts(viewer, owner):
	return (
		Post.objects.filter(author=owner, parent_post__isnull=True)
		.select_related(
			"author",
			"author__profile",
			"reposted_post",
			"reposted_post__author",
			"reposted_post__author__profile",
		)
		.annotate(
			is_liked=Exists(Like.objects.filter(user=viewer, post=OuterRef("pk"))),
			is_bookmarked=Exists(
				Bookmark.objects.filter(user=viewer, post=OuterRef("pk"))
			),
		)
		.order_by("-created_at")
	)


class RegisterView(View):
	template_name = "accounts/register.html"

	def dispatch(self, request, *args, **kwargs):
		if request.user.is_authenticated:
			return redirect("posts:home")
		return super().dispatch(request, *args, **kwargs)

	def get(self, request):
		form = RegisterForm()
		return render(request, self.template_name, {"form": form})

	def post(self, request):
		form = RegisterForm(request.POST or None, request.FILES or None)
		if form.is_valid():
			user = form.save()
			Profile.objects.create(
				user=user,
				avatar=form.cleaned_data.get("avatar"),
				cover_image=form.cleaned_data.get("cover_image"),
			)
			login(request, user)
			return redirect("posts:home")
		return render(request, self.template_name, {"form": form})


class LoginView(View):
	template_name = "accounts/login.html"

	def dispatch(self, request, *args, **kwargs):
		if request.user.is_authenticated:
			return redirect("posts:home")
		return super().dispatch(request, *args, **kwargs)

	def _build_form(self, request):
		form = AuthenticationForm(request, data=request.POST or None)
		form.fields["username"].widget.attrs.update(
			{"class": "auth__input", "placeholder": "Ваш нікнейм"}
		)
		form.fields["password"].widget.attrs.update(
			{"class": "auth__input", "placeholder": "Пароль"}
		)
		return form

	def get(self, request):
		form = self._build_form(request)
		return render(request, self.template_name, {"form": form})

	def post(self, request):
		form = self._build_form(request)
		if form.is_valid():
			user = form.get_user()
			login(request, user)
			return redirect(request.GET.get("next") or "posts:home")
		return render(request, self.template_name, {"form": form})


class LogoutView(View):
	def _logout_and_redirect(self, request):
		logout(request)
		next_url = request.POST.get("next") or request.GET.get("next")
		return redirect(next_url or "posts:home")

	def get(self, request):
		return self._logout_and_redirect(request)

	def post(self, request):
		return self._logout_and_redirect(request)


class UsernameCheckView(View):
	def get(self, request):
		username = (request.GET.get("username") or "").strip()

		if len(username) < 3:
			return JsonResponse(
				{"available": False, "message": "Мінімум 3 символи"}, status=200
			)

		is_taken = User.objects.filter(username__iexact=username).exists()
		if is_taken:
			return JsonResponse(
				{"available": False, "message": "Нік зайнятий"}, status=200
			)

		return JsonResponse({"available": True, "message": "Нік вільний"}, status=200)


class ProfileView(LoginRequiredMixin, View):
	def get(self, request):
		profile, _ = Profile.objects.get_or_create(user=request.user)
		total_likes = Like.objects.filter(post__author=profile.user).count()
		posts = get_profile_posts(request.user, profile.user)
		return render(
			request,
			"accounts/profile.html",
			{
				"profile": profile,
				"is_owner": True,
				"follow_state": None,
				"total_likes": total_likes,
				"posts": posts,
			},
		)


class ProfileDetailView(LoginRequiredMixin, View):
	def get(self, request, username):
		user = get_object_or_404(User, username=username)
		profile, _ = Profile.objects.get_or_create(user=user)
		viewer_profile, _ = Profile.objects.get_or_create(user=request.user)
		total_likes = Like.objects.filter(post__author=profile.user).count()
		posts = get_profile_posts(request.user, profile.user)

		following = profile.followers.filter(pk=viewer_profile.pk).exists()
		followed_by = profile.following.filter(pk=viewer_profile.pk).exists()

		if following and followed_by:
			follow_state = "friends"
		elif followed_by and not following:
			follow_state = "mutual"
		elif following:
			follow_state = "following"
		else:
			follow_state = "none"

		return render(
			request,
			"accounts/profile.html",
			{
				"profile": profile,
				"is_owner": user == request.user,
				"follow_state": follow_state,
				"total_likes": total_likes,
				"posts": posts,
			},
		)


class ProfileEditView(LoginRequiredMixin, View):
	template_name = "accounts/profile_edit.html"

	def _build_form(self, request, profile):
		return ProfileForm(
			request.POST or None,
			request.FILES or None,
			instance=profile,
			user=request.user,
		)

	def get(self, request):
		profile, _ = Profile.objects.get_or_create(user=request.user)
		form = self._build_form(request, profile)
		return render(
			request,
			self.template_name,
			{"form": form, "profile": profile},
		)

	def post(self, request):
		profile, _ = Profile.objects.get_or_create(user=request.user)
		form = self._build_form(request, profile)
		if form.is_valid():
			form.save()
			return redirect("accounts:profile")
		return render(
			request,
			self.template_name,
			{"form": form, "profile": profile},
		)


class ThemePreferencesView(LoginRequiredMixin, View):
	def post(self, request):
		profile, _ = Profile.objects.get_or_create(user=request.user)

		data = {}
		if request.content_type == "application/json":
			try:
				data = json.loads(request.body or "{}")
			except json.JSONDecodeError:
				data = {}
		else:
			data = request.POST

		allowed_themes = {"dark", "light"}
		allowed_accents = {"default", "blue", "purple", "pink", "orange"}

		updates = []
		if (theme := data.get("theme")) in allowed_themes:
			profile.theme_preference = theme
			updates.append("theme_preference")
		if (accent := data.get("accent")) in allowed_accents:
			profile.accent_preference = accent
			updates.append("accent_preference")

		if updates:
			profile.save(update_fields=updates)

		return JsonResponse(
			{
				"theme": profile.theme_preference,
				"accent": profile.accent_preference,
			}
		)
