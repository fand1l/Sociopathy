from django import forms

from .models import ChatGroup, ChatGroupMembership, ChatGroupMessage, ChatMessage


class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ["text", "image", "file"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Напишіть повідомлення...",
                }
            )
        }

    def clean(self):
        cleaned_data = super().clean()
        text = (cleaned_data.get("text") or "").strip()
        image = cleaned_data.get("image")
        file = cleaned_data.get("file")

        if not text and not image and not file:
            raise forms.ValidationError("Повідомлення має містити текст або медіа.")

        return cleaned_data


class ChatGroupForm(forms.ModelForm):
    class Meta:
        model = ChatGroup
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Назва групи",
                }
            )
        }


class ChatGroupMessageForm(forms.ModelForm):
    class Meta:
        model = ChatGroupMessage
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Напишіть повідомлення...",
                }
            )
        }

    def clean_text(self):
        text = (self.cleaned_data.get("text") or "").strip()
        if not text:
            raise forms.ValidationError("Повідомлення має містити текст.")
        return text


class ChatGroupMemberAddForm(forms.Form):
    username = forms.CharField(max_length=150)


class ChatGroupRoleForm(forms.Form):
    role = forms.ChoiceField(
        choices=[
            (ChatGroupMembership.Role.MEMBER, "Учасник"),
            (ChatGroupMembership.Role.ADMIN, "Адмін"),
        ]
    )
