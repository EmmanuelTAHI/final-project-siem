"""
Verrou lecture-seule pour le compte spectateur démo (lien magique / QR code).

Volontairement implémenté en middleware Django plutôt qu'en permission DRF :
une permission déclarée sur une vue (`permission_classes = [...]`) REMPLACE
entièrement la liste par défaut de settings, elle ne s'y ajoute pas — deux
ViewSets du projet (CorrelationRuleViewSet, TicketViewSet) n'en déclarent
aucune et héritent donc du défaut `IsAuthenticated` seul, sans restriction de
rôle. Un middleware, lui, s'exécute pour CHAQUE requête avant qu'aucune vue
ne soit atteinte, quelle que soit sa configuration de permissions — même une
vue future qui oublierait de restreindre l'écriture reste bloquée ici.

Le token JWT est décodé directement (indépendamment de request.user, qui
n'est peuplé par DRF qu'à l'intérieur du dispatch de la vue, donc trop tard
pour un middleware Django classique) pour lire la claim `is_demo_spectator`
posée à l'émission du token (voir apps.authentication.views._issue_jwt_for_user).
"""
from django.http import JsonResponse
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

# Actions de gestion de SA PROPRE session — ne touchent aucune donnée
# métier, seules exemptées du blocage en écriture.
ALLOWED_WRITE_PATHS = (
    "/api/auth/token/refresh/",
    "/api/auth/logout/",
)


class DemoSpectatorReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in SAFE_METHODS and request.path not in ALLOWED_WRITE_PATHS:
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer "):
                try:
                    token = AccessToken(auth_header[len("Bearer "):])
                except TokenError:
                    token = None
                if token is not None and token.get("is_demo_spectator"):
                    return JsonResponse(
                        {
                            "success": False,
                            "message": "Mode démonstration : lecture seule, action non autorisée.",
                        },
                        status=403,
                    )
        return self.get_response(request)
