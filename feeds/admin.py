from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Feed, FeedItem


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "last_fetched", "added_at", "item_count")
    list_filter = ("last_fetched", "added_at")
    search_fields = ("title", "url")
    readonly_fields = ("added_at", "last_fetched")
    ordering = ("-last_fetched", "-added_at")

    def item_count(self, obj):
        return obj.items.count()

    item_count.short_description = "Items"

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ("url",)
        return self.readonly_fields


@admin.register(FeedItem)
class FeedItemAdmin(admin.ModelAdmin):
    list_display = ("title", "feed", "published_at", "is_read", "created_at")
    list_filter = ("is_read", "feed", "published_at", "created_at")
    search_fields = ("title", "content", "feed__title", "feed__url")
    readonly_fields = ("created_at",)
    ordering = ("-published_at", "-created_at")
    date_hierarchy = "published_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("feed")

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    mark_as_read.short_description = "Mark selected items as read"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)

    mark_as_unread.short_description = "Mark selected items as unread"

    actions = ["mark_as_read", "mark_as_unread"]

    def get_list_display_links(self, request, list_display):
        return ["title"]

    def get_ordering(self, request):
        if "is_read" in request.GET:
            return ("is_read", "-published_at")
        return super().get_ordering(request)
