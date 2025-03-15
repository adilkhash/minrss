from rest_framework import serializers
from .models import Feed, FeedItem


class FeedSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Feed
        fields = ("id", "url", "title", "added_at", "item_count")
        read_only_fields = ("added_at", "item_count")

    def get_item_count(self, obj) -> int:
        return obj.items.count()

    def validate_url(self, value: str) -> str:
        from .feed_utils import validate_feed_url

        is_valid = validate_feed_url(value)
        if not is_valid:
            raise serializers.ValidationError("Error while validating URL")
        return value


class FeedItemSerializer(serializers.ModelSerializer):
    feed_title = serializers.CharField(source="feed.title", read_only=True)
    feed_url = serializers.URLField(source="feed.url", read_only=True)

    class Meta:
        model = FeedItem
        fields = (
            "id",
            "feed",
            "feed_title",
            "feed_url",
            "title",
            "content",
            "published_at",
            "is_read",
            "guid",
            "created_at",
        )
        read_only_fields = ("guid", "created_at")
