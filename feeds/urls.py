from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"feeds", views.FeedViewSet, basename="feed")
router.register(r"items", views.FeedItemViewSet, basename="feeditem")

urlpatterns = [
    path("", include(router.urls)),
]
