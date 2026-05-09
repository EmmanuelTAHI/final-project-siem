"""WebSocket URL routing pour Django Channels."""
from django.urls import re_path

from .consumers import AlertNotificationConsumer

websocket_urlpatterns = [
    re_path(r"^ws/notifications/(?P<user_id>[^/]+)/$", AlertNotificationConsumer.as_asgi()),
]
