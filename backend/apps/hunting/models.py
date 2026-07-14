"""
Threat Hunting — requêtes de chasse aux menaces sauvegardées.
"""
import uuid

from django.db import models


class HuntingQuery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="hunting_queries",
        verbose_name="Organisation",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    query_params = models.JSONField(
        default=dict,
        help_text="Filtres: {action, outcome, severity, source_type, geo_country, user_email, source_ip, date_from, date_to, extra_fields}",
    )
    mitre_tactic = models.CharField(max_length=100, blank=True)
    mitre_technique = models.CharField(max_length=100, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_results_count = models.PositiveIntegerField(default=0)
    run_count = models.PositiveIntegerField(default=0)
    is_scheduled = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="hunting_queries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class HuntingResult(models.Model):
    """Résultats d'une exécution de requête de chasse."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="hunting_results",
        verbose_name="Organisation",
        help_text="Dénormalisé depuis query.organization pour l'isolation multi-tenant.",
    )
    query = models.ForeignKey(HuntingQuery, on_delete=models.CASCADE, related_name="results")
    log = models.ForeignKey("logs.NormalizedLog", on_delete=models.CASCADE)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]
        unique_together = [("query", "log")]

    def save(self, *args, **kwargs):
        if self.query_id and not self.organization_id:
            self.organization_id = self.query.organization_id
        super().save(*args, **kwargs)
