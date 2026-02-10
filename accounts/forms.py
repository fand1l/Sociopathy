from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

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
