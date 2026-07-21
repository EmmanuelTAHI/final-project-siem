import uuid

from django.db import models
from django.utils.text import slugify


class Organization(models.Model):
    """
    Un tenant de la plateforme SaaS Log+ : une PME ou un particulier.
    Toutes les données métier (logs, connecteurs, alertes...) sont rattachées
    à une organisation et ne doivent jamais être visibles en dehors de celle-ci
    (voir utils.tenant.OrganizationFilterBackend).
    """

    PLAN_CHOICES = [
        ("free", "Free"),
        ("pro", "Pro"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    is_active = models.BooleanField(default=True)
    is_platform_internal = models.BooleanField(
        default=False,
        help_text="Organisation technique interne (bootstrap/legacy), masquée aux utilisateurs normaux.",
    )
    is_demo = models.BooleanField(
        default=False,
        help_text=(
            "Tenant de démonstration public (lien magique / QR code) : "
            "isolé comme n'importe quel tenant, mais ses actions à effet de "
            "bord réel (emails, webhooks, blocages IP) sont simulées et ses "
            "données sont réinitialisables via `reset_demo_tenant`."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @staticmethod
    def generate_unique_slug(name: str) -> str:
        base = slugify(name)[:190] or "org"
        slug = base
        suffix = 1
        while Organization.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base}-{suffix}"
        return slug
