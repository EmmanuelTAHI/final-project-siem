"""
Isolation multi-tenant — Couche 2 (défense en profondeur, hors DRF).

Convention pour tout nouveau code métier (tâches Celery, management
commands, scripts) qui n'est pas déjà scopé par OrganizationFilterBackend :
utiliser `Model.scoped.for_user(user)` plutôt qu'un `.filter(organization=...)`
ad hoc, pour que la logique de scoping vive à un seul endroit par famille de
modèle.
"""
from django.db import models


class OrganizationScopedManager(models.Manager):
    def for_user(self, user):
        if user.is_superuser:
            return self.all()
        return self.filter(organization_id=user.organization_id)
