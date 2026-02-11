import json

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import RegisterForm, ProfileForm
from .models import Profile
from likes.models import Like

User = get_user_model()


@require_http_methods(["GET", "POST"])
def register_view(request):
	if request.user.is_authenticated:
		return redirect("posts:home")

	form = RegisterForm(request.POST or None, request.FILES or None)
	if request.method == "POST" and form.is_valid():
		user = form.save()
		Profile.objects.create(
			user=user,
			avatar=form.cleaned_data.get("avatar"),
			cover_image=form.cleaned_data.get("cover_image"),
		)
		login(request, user)
		return redirect("posts:home")

	return render(request, "accounts/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request):
	if request.user.is_authenticated:
		return redirect("posts:home")

	form = AuthenticationForm(request, data=request.POST or None)
	form.fields["username"].widget.attrs.update(
		{"class": "auth__input", "placeholder": "Ваш нікнейм"}
	)
	form.fields["password"].widget.attrs.update(
		{"class": "auth__input", "placeholder": "Пароль"}
	)
	if request.method == "POST" and form.is_valid():
		user = form.get_user()
		login(request, user)
		return redirect(request.GET.get("next") or "posts:home")

	return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
	logout(request)
	next_url = request.GET.get("next")
	return redirect(next_url or "posts:home")


@require_GET
def username_check(request):
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


@login_required
def profile_view(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	total_likes = Like.objects.filter(post__author=profile.user).count()
	return render(
		request,
		"accounts/profile.html",
		{
			"profile": profile,
			"is_owner": True,
			"follow_state": None,
			"total_likes": total_likes,
		},
	)


@login_required
def profile_detail_view(request, username):
	user = get_object_or_404(User, username=username)
	profile, _ = Profile.objects.get_or_create(user=user)
	viewer_profile, _ = Profile.objects.get_or_create(user=request.user)
	total_likes = Like.objects.filter(post__author=profile.user).count()

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
		},
	)


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	form = ProfileForm(
		request.POST or None,
		request.FILES or None,
		instance=profile,
		user=request.user,
	)

	if request.method == "POST" and form.is_valid():
		form.save()
		return redirect("accounts:profile")

	return render(
		request,
		"accounts/profile_edit.html",
		{"form": form, "profile": profile},
	)


@login_required
@require_POST
def theme_preferences_view(request):
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
