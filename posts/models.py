from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from django.db.models.functions import Length

class Post(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    content = models.TextField(
        verbose_name="Текст поста"
    )

    image = models.ImageField(
        upload_to='post_images',
        blank=True,
        null=True,
    )

    recommendation_score = models.FloatField(
        default=0.0,
        db_index=True
    )

    parent_post = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def update_score(self):
        likes_count = self.likes.count()
        
        stats = self.replies.annotate(
            content_len=Length('content')
        ).aggregate(
            long_comments=Count('id', filter=Q(content_len__gt=20)),
            short_comments=Count('id', filter=Q(content_len__lte=20))
        )

        current_score = (likes_count * 1.0) + \
                        (stats['long_comments'] * 0.4) + \
                        (stats['short_comments'] * 0.2)

        hours_old = (timezone.now() - self.created_at).total_seconds() / 3600
        time_penalty = hours_old * 0.2 
        
        self.recommendation_score = max(current_score - time_penalty, 0)
        Post.objects.filter(pk=self.pk).update(recommendation_score=self.recommendation_score)

    def __str__(self):
        return f"Post {self.id} by {self.author} (Score: {self.recommendation_score:.2f})"
