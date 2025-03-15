from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Feed, FeedItem
from .serializers import FeedSerializer, FeedItemSerializer
from .feed_utils import fetch_feed_content, create_feed_items


class FeedViewSet(viewsets.ModelViewSet):
    queryset = Feed.objects.all()
    serializer_class = FeedSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feed = serializer.save()

        # Fetch initial content
        items = fetch_feed_content(feed.url)
        if items:
            create_feed_items(feed, items)
            feed.mark_as_fetched()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put"])
    def mark_all_read(self, request, pk=None):
        feed = self.get_object()
        feed.items.filter(is_read=False).update(is_read=True)
        return Response({"status": "all items marked as read"})

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        feed = self.get_object()
        items, error = fetch_feed_content(feed)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        if items:
            created_count = create_feed_items(feed, items)
            feed.mark_as_fetched()
            return Response({"status": "feed refreshed", "new_items": created_count})
        return Response({"status": "no new items found"})


class FeedItemViewSet(viewsets.ModelViewSet):
    queryset = FeedItem.objects.all()
    serializer_class = FeedItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_read", "feed"]
    search_fields = ["title", "content"]
    ordering_fields = ["published_at", "created_at"]
    ordering = ["-published_at"]

    def get_queryset(self):
        queryset = FeedItem.objects.select_related("feed")

        # Filter by read/unread status if specified
        is_read = self.request.query_params.get("is_read", None)
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")

        return queryset

    @action(detail=False, methods=["put"])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"status": "all items marked as read"})

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
