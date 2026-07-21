"""
Génère le lien magique + le QR code pour la démonstration publique (soutenance).

Usage :
    python manage.py generate_demo_link
    python manage.py generate_demo_link --hours 8 --qr-out demo_qr.png

Par défaut le lien est permanent (10 ans) : une fois généré, il reste actif
jusqu'à ce qu'on le révoque explicitement (--hours pour un lien à durée
limitée, ou en désactivant le compte spectateur / le tenant démo). Le token
embarque sa propre durée de vie (voir demo_access_service).
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.authentication.services.demo_access_service import generate_demo_token
from apps.organizations.management.commands.setup_demo_tenant import DEMO_USER_EMAIL
from apps.users.models import User


class Command(BaseCommand):
    help = "Génère le lien magique + QR code d'accès démo (spectateur, sans mot de passe/OTP)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours", type=float, default=87600.0,
            help="Durée de validité du lien en heures (défaut : 87600h ≈ 10 ans, autrement dit permanent).",
        )
        parser.add_argument(
            "--qr-out", type=str, default="demo_qr.png",
            help="Chemin du fichier PNG du QR code à générer (défaut : demo_qr.png).",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.select_related("organization").get(email=DEMO_USER_EMAIL)
        except User.DoesNotExist:
            raise CommandError(
                "Compte démo introuvable — lancez d'abord `python manage.py setup_demo_tenant`."
            )
        if not user.is_demo_spectator:
            raise CommandError(
                "Ce compte n'est pas marqué is_demo_spectator=True — vérifiez setup_demo_tenant."
            )

        max_age_seconds = int(options["hours"] * 3600)
        token = generate_demo_token(user.id, max_age_seconds)

        # FRONTEND_URL sert de base : en prod, nginx sert le frontend et
        # proxy-passe /api/ vers le backend sur le même domaine
        # (https://argussiem.com) — voir nginx/.
        base = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
        url = f"{base}/api/auth/demo-access/{token}/"

        try:
            import qrcode
        except ImportError:
            raise CommandError("Le package `qrcode` n'est pas installé (voir requirements.txt).")

        qr_path = options["qr_out"]
        qrcode.make(url).save(qr_path)

        self.stdout.write(self.style.SUCCESS(f"Lien magique (valide {options['hours']}h) :"))
        self.stdout.write(url)
        self.stdout.write(self.style.SUCCESS(f"QR code enregistré : {qr_path}"))
