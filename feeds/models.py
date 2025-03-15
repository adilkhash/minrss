from django.db import models
from django.utils import timezone


class Feed(models.Model):
    url = models.URLField(unique=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['url']),
            models.Index(fields=['last_fetched']),
        ]

    def __str__(self):
        return self.title or self.url

    def mark_as_fetched(self):
        self.last_fetched = timezone.now()
        self.save()


class FeedItem(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=255)
    content = models.TextField()
    published_at = models.DateTimeField()
    is_read = models.BooleanField(default=False)
    guid = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['feed', 'guid']),
            models.Index(fields=['feed', 'published_at']),
            models.Index(fields=['is_read']),
        ]
        unique_together = ['feed', 'guid']
        ordering = ['-published_at']

    def __str__(self):
        return f"{self.feed.title or self.feed.url} - {self.title}"

    def mark_as_read(self):
        self.is_read = True
        self.save()
