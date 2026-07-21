"""
ASGI config — Django Channels pour WebSockets + HTTP classique.
PFE Argus — TAHI Ezan Franck Emmanuel — 2025-2026
"""
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

django_asgi_app = get_asgi_application()

from apps.notifications.middleware import JWTAuthMiddleware  # noqa: E402
from apps.notifications.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # JWTAuthMiddleware (pas AuthMiddlewareStack) : le frontend n'utilise que
    # des JWT Bearer, jamais de cookie de session Django — voir middleware.py.
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
