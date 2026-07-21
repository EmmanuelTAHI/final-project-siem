"""
Format de réponse standardisé pour toutes les vues de l'API Argus.
Format uniforme : {"status", "data", "message", "pagination"}
"""
from rest_framework import status
from rest_framework.response import Response


def success_response(
    data=None,
    message: str = "Opération réussie.",
    http_status: int = status.HTTP_200_OK,
    pagination: dict = None,
) -> Response:
    """
    Retourne une réponse JSON avec le statut 'success'.

    Args:
        data: Les données à retourner (objet, liste ou None).
        message: Message lisible décrivant l'opération.
        http_status: Code HTTP à retourner.
        pagination: Dictionnaire de pagination optionnel.

    Returns:
        Response DRF avec le format standardisé.
    """
    response_data = {
        "status": "success",
        "data": data,
        "message": message,
    }
    if pagination is not None:
        response_data["pagination"] = pagination
    return Response(response_data, status=http_status)


def error_response(
    message: str = "Une erreur est survenue.",
    errors=None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    """
    Retourne une réponse JSON avec le statut 'error'.

    Args:
        message: Message d'erreur lisible.
        errors: Détails des erreurs de validation (dict ou list).
        http_status: Code HTTP à retourner.

    Returns:
        Response DRF avec le format standardisé.
    """
    response_data = {
        "status": "error",
        "data": None,
        "message": message,
    }
    if errors is not None:
        response_data["errors"] = errors
    return Response(response_data, status=http_status)


def created_response(
    data=None,
    message: str = "Ressource créée avec succès.",
) -> Response:
    """Raccourci pour les réponses 201 Created."""
    return success_response(data=data, message=message, http_status=status.HTTP_201_CREATED)


def no_content_response(message: str = "Ressource supprimée.") -> Response:
    """Raccourci pour les réponses 204 No Content."""
    return Response(
        {"status": "success", "data": None, "message": message},
        status=status.HTTP_204_NO_CONTENT,
    )
