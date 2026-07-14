"""
Middleware Channels — authentifie les connexions WebSocket via JWT.

channels.auth.AuthMiddlewareStack authentifie via les sessions Django
(cookies), mais le frontend Next.js utilise exclusivement des JWT Bearer pour
l'API REST — il n'y a jamais de cookie de session Django. Sans ce middleware,
scope["user"] était donc AnonymousUser sur toutes les connexions WebSocket
réelles, et la couche notifications n'avait aucune authentification effective
(seule l'obscurité de connaître un user_id dans l'URL la protégeait).

Le navigateur ne pouvant pas fixer de header Authorization sur un handshake
WebSocket, le token est passé en query string : wss://.../ws/notifications/?token=...
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _get_user_from_token(raw_token: str):
    from apps.users.models import User

    try:
        validated = AccessToken(raw_token)
        user_id = validated["user_id"]
        return User.objects.get(id=user_id, is_active=True)
    except (InvalidToken, TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]

        scope["user"] = await _get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
