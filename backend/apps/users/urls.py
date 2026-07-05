from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuditTrailViewSet, UserViewSet

router = DefaultRouter()
# audit-trail DOIT être enregistré avant UserViewSet (préfixe r"") : sinon la
# route détail générée par UserViewSet (^(?P<pk>...)/$) intercepte
# /api/users/audit-trail/ en traitant "audit-trail" comme un pk utilisateur
# (Django résout les URLs dans l'ordre d'enregistrement du routeur) → 404.
router.register(r"audit-trail", AuditTrailViewSet, basename="audit-trail")
router.register(r"", UserViewSet, basename="users")

urlpatterns = [
    path("", include(router.urls)),
]
