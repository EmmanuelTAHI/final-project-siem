from django.core.management.base import BaseCommand

from apps.correlation.default_rules import seed_default_rules_for_organization
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = (
        "Crée les règles de corrélation par défaut pour chaque organisation "
        "active qui ne les a pas encore (idempotent). Remplace l'ancien "
        "fixture global default_rules.json, incompatible avec le multi-tenant."
    )

    def handle(self, *args, **options):
        total_created = 0
        for org in Organization.objects.filter(is_active=True):
            created = seed_default_rules_for_organization(org)
            if created:
                self.stdout.write(f"  {org.name} : {created} règle(s) créée(s)")
            total_created += created

        self.stdout.write(self.style.SUCCESS(f"Terminé — {total_created} règle(s) créée(s) au total."))
