"""
Gestionnaire d'erreurs global pour Django REST Framework.
Convertit toutes les exceptions DRF au format de réponse standardisé.
"""
import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied as DRFPermissionDenied,
    Throttled,
    ValidationError as DRFValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context) -> Response:
    """
    Gestionnaire d'exceptions global DRF.
    Retourne toujours le format standardisé : {"status", "data", "message", "errors"}.
    """
    # Appel du handler par défaut DRF
    response = exception_handler(exc, context)

    if response is not None:
        # Exception DRF standard
        error_message = _extract_message(exc, response)
        errors = _extract_errors(response.data)

        response.data = {
            "status": "error",
            "data": None,
            "message": error_message,
            "errors": errors,
        }
        return response

    # Exceptions Django non gérées par DRF
    if isinstance(exc, Http404):
        return Response(
            {
                "status": "error",
                "data": None,
                "message": "La ressource demandée n'existe pas.",
                "errors": None,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, PermissionDenied):
        return Response(
            {
                "status": "error",
                "data": None,
                "message": "Vous n'avez pas la permission d'effectuer cette action.",
                "errors": None,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if isinstance(exc, ValidationError):
        return Response(
            {
                "status": "error",
                "data": None,
                "message": "Erreur de validation.",
                "errors": exc.message_dict if hasattr(exc, "message_dict") else str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Erreur inattendue — log en production
    logger.exception("Erreur non gérée dans l'API Log+", exc_info=exc)
    return Response(
        {
            "status": "error",
            "data": None,
            "message": "Erreur interne du serveur. Contactez l'administrateur.",
            "errors": None,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _extract_message(exc, response) -> str:
    """Extrait le message d'erreur lisible depuis l'exception."""
    if isinstance(exc, NotAuthenticated):
        return "Authentification requise. Fournissez un token JWT valide."
    if isinstance(exc, AuthenticationFailed):
        return "Authentification échouée. Identifiants incorrects."
    if isinstance(exc, DRFPermissionDenied):
        return str(exc.detail) if hasattr(exc, "detail") else "Permission refusée."
    if isinstance(exc, NotFound):
        return "La ressource demandée n'existe pas."
    if isinstance(exc, Throttled):
        wait = getattr(exc, "wait", None)
        if wait:
            return f"Trop de requêtes. Réessayez dans {int(wait)} secondes."
        return "Trop de requêtes. Veuillez patienter."
    if isinstance(exc, DRFValidationError):
        return "Données de requête invalides. Vérifiez les champs fournis."
    if isinstance(exc, APIException):
        return str(exc.detail) if hasattr(exc, "detail") else str(exc)
    return "Une erreur est survenue."


def _extract_errors(data) -> dict | list | None:
    """Extrait les erreurs de validation depuis la réponse DRF."""
    if isinstance(data, dict):
        if "detail" in data and len(data) == 1:
            return None
        if "status" in data:
            return None
        return {k: v if isinstance(v, list) else [v] for k, v in data.items()}
    if isinstance(data, list):
        return data
    return None
