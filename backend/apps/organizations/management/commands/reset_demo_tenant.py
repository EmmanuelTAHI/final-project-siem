"""
Réinitialise les données du tenant de démonstration publique après une
soutenance : supprime tout ce que le(s) spectateur(s) ont pu créer
(alertes, règles, tickets, hunts...), puis réensemence les règles par
défaut. Le compte spectateur et le tenant lui-même sont conservés — seul
leur contenu est remis à zéro.

Usage :
    python manage.py reset_demo_tenant
    python manage.py reset_demo_tenant --dry-run
"""
from django.apps import apps as django_apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError

from apps.organizations.management.commands.setup_demo_tenant import DEMO_ORG_SLUG
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Réinitialise les données du tenant de démonstration (garde le tenant et le compte spectateur)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche ce qui serait supprimé sans rien supprimer.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(slug=DEMO_ORG_SLUG, is_demo=True)
        except Organization.DoesNotExist:
            raise CommandError(
                "Tenant démo introuvable — lancez d'abord `python manage.py setup_demo_tenant`."
            )

        dry_run = options["dry_run"]

        # Tout modèle scopé par organisation est concerné, à l'exception de
        # User (le compte spectateur doit survivre au reset) et Organization
        # elle-même.
        scoped_models = [
            model for model in django_apps.get_models()
            if model._meta.app_label != "users" and model is not Organization
            and any(f.name == "organization" for f in model._meta.get_fields())
        ]

        if dry_run:
            total = 0
            for model in scoped_models:
                count = model.objects.filter(organization=organization).count()
                if count:
                    total += count
                    self.stdout.write(f"  [dry-run] {model._meta.app_label}.{model.__name__}: {count} ligne(s)")
            self.stdout.write(self.style.WARNING(f"Dry-run — {total} ligne(s) seraient supprimées."))
            return

        # Suppression multi-passes : certains modèles se protègent
        # mutuellement (on_delete=PROTECT) selon l'ordre de suppression, donc
        # on retente les modèles en échec tant que la suppression globale
        # progresse encore.
        remaining = list(scoped_models)
        total = 0
        while remaining:
            progressed = False
            still_remaining = []
            for model in remaining:
                qs = model.objects.filter(organization=organization)
                count = qs.count()
                if not count:
                    continue
                try:
                    qs.delete()
                    total += count
                    progressed = True
                    self.stdout.write(f"  {model._meta.app_label}.{model.__name__}: {count} ligne(s) supprimée(s)")
                except ProtectedError:
                    still_remaining.append(model)
            if not progressed:
                if still_remaining:
                    labels = ", ".join(f"{m._meta.app_label}.{m.__name__}" for m in still_remaining)
                    raise CommandError(f"Suppression bloquée (PROTECT) pour : {labels}")
                break
            remaining = still_remaining

        from apps.correlation.default_rules import seed_default_rules_for_organization
        created = seed_default_rules_for_organization(organization)

        self.stdout.write(self.style.SUCCESS(
            f"Tenant démo réinitialisé ({total} ligne(s) supprimée(s)), "
            f"{created} règle(s) par défaut réensemencée(s)."
        ))
