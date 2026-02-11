from django.db import models
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.templatetags.static import static

class CustomUser(AbstractUser):
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_set",
        blank=True,
        verbose_name="Групи"
    )

    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_set",
        blank=True,
        verbose_name="Дозволи користувача"
    )

    def __str__(self):
        return self.username
    

class Profile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    username_last_changed = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Остання зміна нікнейму"
    )

    bio = models.TextField(
        max_length=500,
        blank=True,
        verbose_name="Опис"
    )

    avatar = models.ImageField(
        null=True,
        blank=True,
        upload_to="profile_pics"
    )

    cover_image = models.ImageField(
        null=True,
        blank=True,
        upload_to='cover_pics'
    )

    following = models.ManyToManyField(
        "self",
        through="relationships.Follow",
        through_fields=("user_from", "user_to"),
        symmetrical=False,
        related_name='followers'
    )

    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, "url"):
            return self.avatar.url
        
        return static('assets/default_avatar.jpg')
    
    @property
    def cover_url(self):
        if self.cover_image and hasattr(self.cover_image, "url"):
            return self.cover_image.url
        return static('assets/default_cover.jpg')
    
    def __str__(self):
        return f"Profile of {self.user.username}"