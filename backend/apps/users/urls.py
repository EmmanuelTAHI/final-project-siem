from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.authentication.views import AcceptInviteView, InviteUserView

from .views import AuditTrailViewSet, UserViewSet

router = DefaultRouter()
# audit-trail DOIT être enregistré avant UserViewSet (préfixe r"") : sinon la
# route détail générée par UserViewSet (^(?P<pk>...)/$) intercepte
# /api/users/audit-trail/ en traitant "audit-trail" comme un pk utilisateur
# (Django résout les URLs dans l'ordre d'enregistrement du routeur) → 404.
router.register(r"audit-trail", AuditTrailViewSet, basename="audit-trail")
router.register(r"", UserViewSet, basename="users")

urlpatterns = [
    # invite/accept-invite AVANT le router : même piège que audit-trail
    # ci-dessus, "invite" serait sinon traité comme un pk utilisateur.
    path("invite/", InviteUserView.as_view(), name="users-invite"),
    path("accept-invite/", AcceptInviteView.as_view(), name="users-accept-invite"),
    path("", include(router.urls)),
]
