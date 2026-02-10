from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from accounts.models import Profile, CustomUser
from .models import Follow


@login_required
@require_POST
def follow_toggle(request, username):
	target_user = get_object_or_404(CustomUser, username=username)
	target_profile = get_object_or_404(Profile, user=target_user)
	actor_profile = get_object_or_404(Profile, user=request.user)

	if target_profile == actor_profile:
		return redirect("accounts:profile")

	relation = Follow.objects.filter(
		user_from=actor_profile,
		user_to=target_profile,
	)

	if relation.exists():
		relation.delete()
	else:
		Follow.objects.create(user_from=actor_profile, user_to=target_profile)

	return redirect("accounts:profile_detail", username=target_user.username)
