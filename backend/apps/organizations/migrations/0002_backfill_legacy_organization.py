"""
Migration de données : bascule de la plateforme mono-tenant vers multi-tenant.

Crée une organisation "legacy" qui devient la zone d'atterrissage de toutes
les données pré-existantes (utilisateurs non-superuser, connecteurs, logs,
alertes, règles...). C'est un backfill nécessaire avant de pouvoir passer les
FK `organization` en not-null (migrations "contract" ultérieures).

Doit être exécutée en production seulement après un pg_dump de sauvegarde et
un essai préalable sur un snapshot en staging (voir le plan multi-tenant).
"""
from django.db import migrations


LEGACY_SLUG = "legacy"


def backfill_legacy_organization(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    User = apps.get_model("users", "User")
    AuditTrail = apps.get_model("users", "AuditTrail")
    ConnectorConfig = apps.get_model("collectors", "ConnectorConfig")
    CollectionJob = apps.get_model("collectors", "CollectionJob")
    RawLog = apps.get_model("logs", "RawLog")
    NormalizedLog = apps.get_model("logs", "NormalizedLog")
    CorrelationRule = apps.get_model("correlation", "CorrelationRule")
    RuleMatch = apps.get_model("correlation", "RuleMatch")
    Alert = apps.get_model("alerts", "Alert")
    MLModel = apps.get_model("ml", "MLModel")
    Prediction = apps.get_model("ml", "Prediction")
    EnrichedLog = apps.get_model("threat_intel", "EnrichedLog")
    Playbook = apps.get_model("soar", "Playbook")
    PlaybookExecution = apps.get_model("soar", "PlaybookExecution")
    HuntingQuery = apps.get_model("hunting", "HuntingQuery")
    HuntingResult = apps.get_model("hunting", "HuntingResult")

    legacy_org, _ = Organization.objects.get_or_create(
        slug=LEGACY_SLUG,
        defaults={
            "name": "Log+ (Legacy)",
            "plan": "free",
            "is_active": True,
            "is_platform_internal": True,
        },
    )

    # Utilisateurs non-superuser sans organisation -> legacy.
    # Les superusers (staff plateforme) restent organization=None.
    User.objects.filter(organization__isnull=True, is_superuser=False).update(
        organization=legacy_org
    )

    AuditTrail.objects.filter(organization__isnull=True).update(organization=legacy_org)

    ConnectorConfig.objects.filter(organization__isnull=True).update(organization=legacy_org)
    CollectionJob.objects.filter(organization__isnull=True).update(organization=legacy_org)

    RawLog.objects.filter(organization__isnull=True).update(organization=legacy_org)
    NormalizedLog.objects.filter(organization__isnull=True).update(organization=legacy_org)

    CorrelationRule.objects.filter(organization__isnull=True).update(organization=legacy_org)
    RuleMatch.objects.filter(organization__isnull=True).update(organization=legacy_org)

    Alert.objects.filter(organization__isnull=True).update(organization=legacy_org)

    MLModel.objects.filter(organization__isnull=True).update(organization=legacy_org)
    Prediction.objects.filter(organization__isnull=True).update(organization=legacy_org)

    EnrichedLog.objects.filter(organization__isnull=True).update(organization=legacy_org)

    Playbook.objects.filter(organization__isnull=True).update(organization=legacy_org)
    PlaybookExecution.objects.filter(organization__isnull=True).update(organization=legacy_org)

    HuntingQuery.objects.filter(organization__isnull=True).update(organization=legacy_org)
    HuntingResult.objects.filter(organization__isnull=True).update(organization=legacy_org)


def noop_reverse(apps, schema_editor):
    """
    Pas de retour arrière automatique : une fois d'autres organisations
    créées, "dé-attribuer" la legacy org perdrait de l'information. Si un
    rollback est nécessaire, restaurer depuis le pg_dump pris avant migration.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
        ("users", "0004_audittrail_organization_user_organization"),
        ("collectors", "0003_collectionjob_organization_and_more"),
        ("logs", "0004_normalizedlog_organization_rawlog_organization_and_more"),
        ("correlation", "0002_correlationrule_organization_rulematch_organization_and_more"),
        ("alerts", "0003_alert_organization"),
        ("ml", "0003_mlmodel_organization_prediction_organization"),
        ("threat_intel", "0003_enrichedlog_organization"),
        ("soar", "0003_playbook_organization_playbookexecution_organization_and_more"),
        ("hunting", "0003_huntingquery_organization_huntingresult_organization"),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_organization, noop_reverse),
    ]
