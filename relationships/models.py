from django.db import models

class Follow(models.Model):
    user_from = models.ForeignKey(
        "accounts.Profile",
        related_name="rel_from_set",
        on_delete=models.CASCADE
    )

    user_to = models.ForeignKey(
        "accounts.Profile",
        related_name="rel_to_set",
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_from', 'user_to')

    def __str__(self):
        return f"{self.user_from} follows {self.user_to}"
