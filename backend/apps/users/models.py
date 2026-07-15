"""
Modèles utilisateurs de Log+.
User étendu (AbstractUser), AuditTrail.
"""
import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models


class LogPlusUserManager(UserManager):
    """Manager personnalisé utilisant l'email comme identifiant principal."""

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Modèle utilisateur Log+ étendu.
    L'email remplace le username comme identifiant principal.
    """

    ROLE_CHOICES = [
        ("admin", "Administrateur"),
        ("analyst", "Analyste SOC"),
        ("viewer", "Observateur"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Adresse email")
    first_name = models.CharField(max_length=150, blank=False, verbose_name="Prénom")
    last_name = models.CharField(max_length=150, blank=False, verbose_name="Nom")
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Organisation",
        help_text="Null uniquement pour le staff plateforme (is_superuser).",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="viewer",
        verbose_name="Rôle",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    email_notifications = models.BooleanField(
        default=True, verbose_name="Notifications par email",
        help_text="Recevoir les notifications de sécurité par email.",
    )
    critical_alert_emails = models.BooleanField(
        default=True, verbose_name="Alertes critiques par email",
        help_text="Notification email immédiate pour les alertes critiques.",
    )
    weekly_report_email = models.BooleanField(
        default=False, verbose_name="Rapport hebdomadaire par email",
        help_text="Recevoir un résumé hebdomadaire de l'activité par email.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = LogPlusUserManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}> [{self.role}]"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_platform_staff(self) -> bool:
        """Staff plateforme (super-admin) : voit toutes les organisations."""
        return self.is_superuser

    def clean(self):
        super().clean()
        if self.organization_id is None and not self.is_superuser:
            raise ValidationError(
                "Un utilisateur non-superuser doit appartenir à une organisation."
            )


class AuditTrail(models.Model):
    """
    Journal d'audit des actions critiques dans Log+.
    Enregistre qui a fait quoi, quand et depuis quelle IP.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_trails",
        verbose_name="Utilisateur",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_trails",
        verbose_name="Organisation",
        help_text="Null pour les évènements système plateforme (visibles du super-admin uniquement).",
    )
    action = models.CharField(
        max_length=100,
        verbose_name="Action",
        help_text="Ex: login, logout, rule_create, alert_update",
    )
    target_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Modèle cible",
        help_text="Ex: Alert, CorrelationRule, ConnectorConfig",
    )
    target_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="ID de la cible",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Adresse IP",
    )
    geo_country = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        verbose_name="Pays (ISO 3166-1 alpha-2)",
    )
    geo_city = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Ville",
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name="User-Agent",
    )
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Données supplémentaires",
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Horodatage")

    class Meta:
        verbose_name = "Audit Trail"
        verbose_name_plural = "Audit Trails"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["target_model", "target_id"]),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else "Système"
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {user_str} → {self.action}"

    @classmethod
    def log(
        cls,
        action: str,
        user=None,
        organization=None,
        target_model: str = "",
        target_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        geo_country: str = None,
        geo_city: str = None,
        extra_data: dict = None,
    ):
        """
        Méthode de classe utilitaire pour créer facilement une entrée d'audit.
        `organization` est déduite de `user.organization` si non fournie
        explicitement ; reste `None` pour un évènement système plateforme
        (visible uniquement du super-admin).
        """
        if organization is None and user is not None:
            organization = user.organization
        return cls.objects.create(
            action=action,
            user=user,
            organization=organization,
            target_model=target_model,
            target_id=str(target_id) if target_id else None,
            ip_address=ip_address,
            user_agent=user_agent,
            geo_country=geo_country or "",
            geo_city=geo_city or "",
            extra_data=extra_data or {},
        )
