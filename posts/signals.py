from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from likes.models import Like

@receiver(post_save, sender=Like)
@receiver(post_delete, sender=Like)
def update_post_score_on_like(sender, instance, **kwargs):
    instance.post.update_score()