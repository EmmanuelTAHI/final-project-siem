"""
Chiffrement Fernet AES-256 pour les credentials et tokens OAuth.
Utilise la clé ENCRYPTION_KEY depuis les variables d'environnement.
"""
import json
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Retourne une instance Fernet avec la clé depuis les settings."""
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY n'est pas définie dans les variables d'environnement. "
            "Générez-en une avec : python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plaintext: str) -> str:
    """
    Chiffre une chaîne de caractères avec Fernet (AES-256-CBC + HMAC-SHA256).

    Args:
        plaintext: La valeur à chiffrer.

    Returns:
        La valeur chiffrée en base64 sous forme de chaîne.
    """
    f = _get_fernet()
    encrypted_bytes = f.encrypt(plaintext.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """
    Déchiffre une valeur chiffrée avec Fernet.

    Args:
        ciphertext: La valeur chiffrée en base64.

    Returns:
        La valeur en clair.

    Raises:
        InvalidToken: Si le token est invalide ou altéré.
    """
    f = _get_fernet()
    try:
        decrypted_bytes = f.decrypt(ciphertext.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken as exc:
        logger.error("Échec du déchiffrement : token invalide ou altéré.")
        raise InvalidToken("Impossible de déchiffrer la valeur.") from exc


def encrypt_dict(data: dict) -> str:
    """
    Sérialise un dictionnaire en JSON puis le chiffre.

    Args:
        data: Le dictionnaire à chiffrer.

    Returns:
        La représentation JSON chiffrée.
    """
    json_str = json.dumps(data, ensure_ascii=False)
    return encrypt_value(json_str)


def decrypt_dict(ciphertext: str) -> dict:
    """
    Déchiffre et désérialise un dictionnaire chiffré.

    Args:
        ciphertext: La chaîne chiffrée contenant du JSON.

    Returns:
        Le dictionnaire déchiffré.
    """
    json_str = decrypt_value(ciphertext)
    return json.loads(json_str)
