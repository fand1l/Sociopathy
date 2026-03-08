from django import forms
from .models import (
    Post,
    PostImage,
    MAX_POST_CONTENT_LENGTH,
    MAX_POST_IMAGES,
    MAX_POST_IMAGE_SIZE_BYTES,
)


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            cleaned = []
            for item in data:
                cleaned.append(super().clean(item, initial))
            return cleaned
        return super().clean(data, initial)

class PostForm(forms.ModelForm):
    images = MultipleImageField(
        required=False,
        widget=MultipleImageInput(attrs={
            'id': 'file-upload',
            'class': 'custom-file-input',
            'accept': 'image/*',
        }),
    )

    class Meta:
        model = Post
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'modal__textarea',
                'placeholder': 'Що у вас на думці?',
                'rows': 4,
            }),
        }

    def clean_content(self):
        content = (self.cleaned_data.get('content') or '').strip()
        uploaded_images = self.files.getlist('images')

        if len(content) > MAX_POST_CONTENT_LENGTH:
            raise forms.ValidationError(
                f"Максимальна довжина поста — {MAX_POST_CONTENT_LENGTH} символів."
            )

        if not content and not uploaded_images and not self._instance_has_images():
            raise forms.ValidationError("Пост не може бути зовсім порожнім!")

        return content

    def clean_images(self):
        uploaded_images = self.files.getlist('images')
        if not uploaded_images:
            return uploaded_images

        if len(uploaded_images) > MAX_POST_IMAGES:
            raise forms.ValidationError(
                f"Максимальна кількість зображень — {MAX_POST_IMAGES}."
            )

        for image in uploaded_images:
            if image.size > MAX_POST_IMAGE_SIZE_BYTES:
                raise forms.ValidationError(
                    "Кожне зображення має бути не більше 10 МБ."
                )

        return uploaded_images

    def save(self, commit=True):
        post = super().save(commit=False)
        uploaded_images = self.files.getlist('images')
        is_update = bool(self.instance and self.instance.pk)

        if uploaded_images:
            post.image = uploaded_images[0]

        if not commit:
            return post

        post.save()

        if uploaded_images:
            if is_update:
                post.extra_images.all().delete()

            if len(uploaded_images) > 1:
                PostImage.objects.bulk_create(
                    [PostImage(post=post, image=image) for image in uploaded_images[1:]]
                )

        return post

    def _instance_has_images(self):
        if not self.instance or not self.instance.pk:
            return False
        return bool(self.instance.image) or self.instance.extra_images.exists()