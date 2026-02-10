from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'modal__textarea',
                'placeholder': 'Що у вас на думці?',
                'rows': 4,
            }),
            'image': forms.FileInput(attrs={
                'id': 'file-upload',
                'class': 'custom-file-input',
            }),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content and not self.files.get('image'):
            raise forms.ValidationError("Пост не може бути зовсім порожнім!")
        return content