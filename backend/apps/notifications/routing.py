"""WebSocket URL routing pour Django Channels."""
from django.urls import re_path

from .consumers import AlertNotificationConsumer

websocket_urlpatterns = [
    # Pas de user_id dans l'URL : l'identité vient exclusivement de
    # scope["user"] (peuplé par JWTAuthMiddleware), jamais d'un paramètre
    # fourni par le client (ancienne faille IDOR).
    re_path(r"^ws/notifications/$", AlertNotificationConsumer.as_asgi()),
]
