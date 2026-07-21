"""
Crée (ou récupère, si déjà existant) le compte "spectateur" utilisé par le
lien magique / QR code de présentation. Idempotent : peut être relancée sans
effet de bord.

Le spectateur est rattaché à une organisation RÉELLE existante (par défaut
celle donnée par --organization-slug) pour que le public voie les vraies
données (logs, alertes...) déjà présentes dessus — pas un tenant vide séparé.
Sa sécurité ne repose PAS sur l'isolation multi-tenant mais sur le flag
`User.is_demo_spectator`, forcé en lecture seule globalement par
DemoSpectatorReadOnlyMiddleware (voir utils/demo_readonly_middleware.py),
quelle que soit l'organisation à laquelle il est rattaché.

Usage :
    python manage.py setup_demo_tenant
    python manage.py setup_demo_tenant --organization-slug legacy
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.organizations.models import Organization
from apps.users.models import User

DEMO_USER_EMAIL = "spectateur@demo.argus.local"
DEFAULT_ORGANIZATION_SLUG = "legacy"


class Command(BaseCommand):
    help = "Crée le compte spectateur démo (lien magique / QR code), rattaché à une organisation réelle."

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-slug", type=str, default=DEFAULT_ORGANIZATION_SLUG,
            help=f"Slug de l'organisation réelle à montrer au public (défaut : {DEFAULT_ORGANIZATION_SLUG}).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options["organization_slug"]
        try:
            organization = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organisation '{slug}' introuvable.")

        user, user_created = User.objects.get_or_create(
            email=DEMO_USER_EMAIL,
            defaults={
                "username": DEMO_USER_EMAIL,
                "first_name": "Spectateur",
                "last_name": "Démo",
                # role="admin" pour avoir un accès en LECTURE complet (les
                # vues qui exigent IsAnalyst/IsAdmin bloqueraient sinon des
                # pages entières, ex. collecteurs, règles de corrélation).
                # Sans risque : DemoSpectatorReadOnlyMiddleware bloque TOUTE
                # écriture pour ce compte quel que soit son rôle — voir
                # utils/demo_readonly_middleware.py.
                "role": "admin",
                "organization": organization,
                "is_active": True,
                "is_demo_spectator": True,
            },
        )
        if user_created:
            # Pas de mot de passe utilisable : l'accès passe uniquement par
            # le lien magique signé (DemoAccessView), jamais par /login/.
            user.set_unusable_password()
            user.save(update_fields=["password"])
        else:
            changed = []
            if user.organization_id != organization.id:
                user.organization = organization
                changed.append("organization")
            if not user.is_demo_spectator:
                user.is_demo_spectator = True
                changed.append("is_demo_spectator")
            if user.role != "admin":
                user.role = "admin"
                changed.append("role")
            if changed:
                user.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS(
            f"Compte spectateur prêt — user_id={user.id} organization={organization.name} "
            f"({'créé' if user_created else 'mis à jour'})."
        ))
