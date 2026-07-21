"""
Crée (ou récupère, si déjà existant) le tenant de démonstration public et son
compte "spectateur" — utilisés par le lien magique / QR code affiché en
soutenance. Idempotent : peut être relancée sans effet de bord.

Usage :
    python manage.py setup_demo_tenant
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.organizations.models import Organization
from apps.users.models import User

DEMO_ORG_SLUG = "demo-spectateurs"
DEMO_ORG_NAME = "Log+ — Démo publique"
DEMO_USER_EMAIL = "spectateur@demo.logplus.local"


class Command(BaseCommand):
    help = "Crée le tenant et le compte de démonstration publique (lien magique / QR code)."

    @transaction.atomic
    def handle(self, *args, **options):
        organization, org_created = Organization.objects.get_or_create(
            slug=DEMO_ORG_SLUG,
            defaults={"name": DEMO_ORG_NAME, "plan": "pro", "is_demo": True},
        )
        if not organization.is_demo:
            organization.is_demo = True
            organization.save(update_fields=["is_demo"])

        user, user_created = User.objects.get_or_create(
            email=DEMO_USER_EMAIL,
            defaults={
                "username": DEMO_USER_EMAIL,
                "first_name": "Spectateur",
                "last_name": "Démo",
                "role": "analyst",
                "organization": organization,
                "is_active": True,
            },
        )
        if user_created:
            # Pas de mot de passe utilisable : l'accès passe uniquement par
            # le lien magique signé (DemoAccessView), jamais par /login/.
            user.set_unusable_password()
            user.save(update_fields=["password"])

        from apps.correlation.default_rules import seed_default_rules_for_organization
        seed_default_rules_for_organization(organization)

        self.stdout.write(self.style.SUCCESS(
            f"Tenant démo prêt — organization_id={organization.id} user_id={user.id} "
            f"({'créés' if org_created or user_created else 'déjà existants'})."
        ))
