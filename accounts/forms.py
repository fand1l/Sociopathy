from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Profile

User = get_user_model()


class RegisterForm(UserCreationForm):
    avatar = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "auth__file", "accept": "image/*"}
        ),
        label="Аватар",
    )
    cover_image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "auth__file", "accept": "image/*"}
        ),
        label="Обкладинка",
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2", "avatar", "cover_image")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "auth__input",
                    "placeholder": "Ваш нікнейм",
                    "autocomplete": "username",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update(
            {
                "class": "auth__input",
                "placeholder": "Пароль",
                "autocomplete": "new-password",
            }
        )
        self.fields["password2"].widget.attrs.update(
            {
                "class": "auth__input",
                "placeholder": "Повторіть пароль",
                "autocomplete": "new-password",
            }
        )


class ProfileForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        label="Нікнейм",
        widget=forms.TextInput(
            attrs={
                "class": "profile__input",
                "placeholder": "Ваш нікнейм",
                "autocomplete": "username",
            }
        ),
    )

    class Meta:
        model = Profile
        fields = ("bio", "avatar", "cover_image")
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "class": "profile__input",
                    "placeholder": "Розкажіть трохи про себе",
                    "rows": 4,
                }
            ),
            "avatar": forms.ClearableFileInput(
                attrs={"class": "profile__file", "accept": "image/*"}
            ),
            "cover_image": forms.ClearableFileInput(
                attrs={"class": "profile__file", "accept": "image/*"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["username"].initial = self.user.username

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Вкажіть нікнейм")

        if self.user is None:
            return username

        if username == self.user.username:
            return username

        last_changed = getattr(self.instance, "username_last_changed", None)
        if last_changed:
            delta = timezone.now() - last_changed
            if delta.days < 7:
                raise ValidationError("Нікнейм можна змінювати раз на 7 днів")

        is_taken = (
            User.objects.filter(username__iexact=username)
            .exclude(pk=self.user.pk)
            .exists()
        )
        if is_taken:
            raise ValidationError("Цей нікнейм уже зайнятий")

        return username

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            new_username = self.cleaned_data.get("username", self.user.username)
            if new_username != self.user.username:
                self.user.username = new_username
                profile.username_last_changed = timezone.now()

        if commit:
            if self.user:
                self.user.save()
            profile.save()
            self.save_m2m()

        return profile
