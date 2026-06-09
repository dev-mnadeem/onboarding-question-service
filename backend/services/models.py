from django.db import models


class Service(models.Model):
    """A line of business. Steps and onboardings are scoped to these."""

    title = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("title",)

    def __str__(self):
        return self.title
