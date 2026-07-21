"""
Service d'accès démo (lien magique / QR code) — voir apps.authentication.views.DemoAccessView.

Contourne volontairement mot de passe + OTP pour un unique compte "spectateur"
rattaché à un tenant marqué `Organization.is_demo=True`. N'émet jamais de
token pour un utilisateur dont l'organisation n'est pas explicitement
marquée démo : ce garde-fou est ce qui empêche ce mécanisme de devenir un
bypass d'authentification général.
"""
from __future__ import annotations

from django.core import signing

DEMO_TOKEN_SALT = "argus_demo_access"


def generate_demo_token(user_id, max_age_seconds: int) -> str:
    """Token signé, auto-porteur de sa propre durée de vie (embarquée dans le payload
    plutôt que dans max_age de verify, pour que la commande puisse choisir la durée
    à la génération sans dépendre d'une constante partagée)."""
    return signing.dumps(
        {"demo_user_id": str(user_id), "ttl": max_age_seconds},
        salt=DEMO_TOKEN_SALT,
    )


def read_demo_token(token: str) -> str:
    """Retourne le user_id encodé. Lève SignatureExpired / BadSignature."""
    # On ne connaît le max_age qu'après un premier décodage non borné du
    # payload signé ; la signature elle-même reste vérifiée dans tous les cas.
    unbound = signing.loads(token, salt=DEMO_TOKEN_SALT)
    ttl = int(unbound.get("ttl") or 0)
    payload = signing.loads(token, salt=DEMO_TOKEN_SALT, max_age=ttl)
    return payload["demo_user_id"]
