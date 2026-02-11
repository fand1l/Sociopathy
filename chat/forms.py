from django import forms

from .models import ChatMessage


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
