"""
Tâches Celery pour l'entraînement et l'inférence du module ML.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ANOMALY_ALERT_THRESHOLD = 0.7


@shared_task(name="apps.ml.tasks.train_isolation_forest", bind=True, max_retries=1)
def train_isolation_forest(
    self, days_of_data: int = 30, contamination: float = None, organization_id: str = None
):
    """
    Entraîne un nouveau modèle Isolation Forest par organisation, sur les
    données récentes de cette organisation uniquement (isolation multi-tenant
    : pas de modèle mutualisé entre tenants).

    - `organization_id` fourni (déclenchement manuel depuis /api/ml/train/) :
      entraîne uniquement cette organisation.
    - `organization_id` omis (planifié chaque dimanche 02h00 UTC par Celery
      Beat) : entraîne toutes les organisations actives.
    """
    from apps.organizations.models import Organization

    if contamination is None:
        contamination = float(getattr(settings, "ML_CONTAMINATION_RATE", 0.05))

    orgs = (
        Organization.objects.filter(pk=organization_id)
        if organization_id
        else Organization.objects.filter(is_active=True)
    )

    results = {}
    for org in orgs:
        try:
            results[str(org.id)] = _train_isolation_forest_for_org(
                org, days_of_data=days_of_data, contamination=contamination
            )
        except Exception as exc:
            logger.exception("Erreur entraînement ML pour l'org %s : %s", org.id, exc)
            results[str(org.id)] = {"status": "error", "reason": str(exc)}
    return results


def _train_isolation_forest_for_org(org, days_of_data: int, contamination: float) -> dict:
    from apps.ml.anomaly_detector import AnomalyDetector
    from apps.ml.models import MLModel

    logger.info(
        "Démarrage entraînement Isolation Forest — org=%s, days=%d, contamination=%.2f",
        org.id, days_of_data, contamination,
    )

    detector = AnomalyDetector()
    try:
        metrics = detector.train(
            organization_id=org.id, days_of_data=days_of_data, contamination=contamination
        )
    except ValueError as exc:
        logger.info("Entraînement ML ignoré pour l'org %s : %s", org.id, exc)
        return {"status": "skipped", "reason": str(exc)}

    version = f"1.{MLModel.objects.filter(organization=org).count()}.0"
    ml_model = MLModel.objects.create(
        organization=org,
        name="Log+ Isolation Forest",
        version=version,
        algorithm="isolation_forest",
        trained_at=timezone.now(),
        is_active=False,
        model_file="placeholder",
        training_samples=metrics["training_samples"],
        contamination_rate=contamination,
    )

    filepath = detector.save_model(ml_model)

    from django.core.files import File
    with open(filepath, "rb") as f:
        ml_model.model_file.save(
            f"isolation_forest_{version}.joblib",
            File(f),
            save=True,
        )

    ml_model.activate()

    logger.info(
        "Modèle ML v%s (org=%s) entraîné et activé avec succès. Métriques : %s",
        version, org.id, metrics,
    )
    return {"status": "success", "version": version, "metrics": metrics}


@shared_task(name="apps.ml.tasks.run_anomaly_detection_on_new_logs", bind=True, max_retries=2)
def run_anomaly_detection_on_new_logs(self):
    """
    Exécute l'inférence ML par organisation active, sur les logs de cette
    organisation uniquement (isolation multi-tenant : un modèle ne voit
    jamais les logs d'une autre org).
    Planifié toutes les 10 minutes par Celery Beat.
    """
    from apps.organizations.models import Organization

    results = {}
    for org in Organization.objects.filter(is_active=True):
        try:
            results[str(org.id)] = _run_anomaly_detection_for_org(org)
        except Exception as exc:
            logger.exception("Erreur inférence ML pour l'org %s : %s", org.id, exc)
            results[str(org.id)] = {"status": "error", "reason": str(exc)}
    return results


def _run_anomaly_detection_for_org(org) -> dict:
    """Si is_anomaly=True et score > ANOMALY_ALERT_THRESHOLD → crée une alerte."""
    from apps.alerts.models import Alert
    from apps.logs.models import NormalizedLog
    from apps.ml.anomaly_detector import AnomalyDetector
    from apps.ml.models import MLModel, Prediction

    try:
        active_ml_model = MLModel.objects.filter(
            is_active=True, organization=org
        ).latest("created_at")
    except MLModel.DoesNotExist:
        return {"status": "skipped", "reason": "no_active_model"}

    detector = AnomalyDetector.load_active_model(organization_id=org.id)
    if not detector:
        return {"status": "error", "reason": "model_load_failed"}

    logs_without_prediction = NormalizedLog.objects.filter(
        organization=org, prediction__isnull=True
    ).order_by("indexed_at")[:1000]

    count = logs_without_prediction.count()
    if count == 0:
        return {"status": "success", "analyzed": 0, "anomalies": 0}

    logger.info("Inférence ML sur %d logs (org=%s)...", count, org.id)

    predictions = detector.predict(logs_without_prediction)

    anomaly_count = 0
    alerts_created = 0

    for pred_data in predictions:
        log_id = pred_data["log_id"]
        is_anomaly = pred_data["is_anomaly"]
        score = pred_data["anomaly_score"]

        try:
            log = NormalizedLog.objects.get(id=log_id)
        except NormalizedLog.DoesNotExist:
            continue

        # Créer la Prediction
        Prediction.objects.get_or_create(
            log=log,
            defaults={
                "model": active_ml_model,
                "is_anomaly": is_anomaly,
                "anomaly_score": score,
            },
        )

        if is_anomaly:
            anomaly_count += 1

        # Créer une alerte si anomalie significative
        if is_anomaly and score >= ANOMALY_ALERT_THRESHOLD:
            existing_alert = Alert.objects.filter(
                status__in=("open", "in_progress"),
                title__icontains="Anomalie ML",
                description__icontains=str(log_id),
                organization=log.organization,
            ).exists()

            if not existing_alert:
                Alert.objects.create(
                    title=f"Anomalie ML détectée — {log.user_email or log.source_ip or 'inconnu'}",
                    description=(
                        f"Le modèle ML (Isolation Forest v{active_ml_model.version}) "
                        f"a détecté une anomalie avec un score de {score:.3f}.\n\n"
                        f"Log ID: {log_id}\n"
                        f"Utilisateur: {log.user_email or 'N/A'}\n"
                        f"IP: {log.source_ip or 'N/A'}\n"
                        f"Action: {log.action}\n"
                        f"Horodatage: {log.event_time.isoformat()}\n"
                        f"Pays: {log.geo_country or 'N/A'}"
                    ),
                    severity="high",
                    status="open",
                    organization=log.organization,
                )
                alerts_created += 1

    logger.info(
        "Inférence terminée : %d logs, %d anomalies, %d alertes créées.",
        count,
        anomaly_count,
        alerts_created,
    )
    return {
        "status": "success",
        "analyzed": count,
        "anomalies": anomaly_count,
        "alerts_created": alerts_created,
    }


@shared_task(name="apps.ml.tasks.retrain_on_false_positives")
def retrain_on_false_positives():
    """
    Boucle de feedback : les alertes marquées false_positive sont utilisées
    pour ajuster le taux de contamination du prochain entraînement.
    Tourne une fois par jour.
    """
    from apps.alerts.models import Alert
    from apps.ml.models import MLModel
    from django.conf import settings

    cutoff = timezone.now() - timedelta(days=30)
    total_alerts = Alert.objects.filter(created_at__gte=cutoff).count()
    fp_alerts = Alert.objects.filter(status="false_positive", created_at__gte=cutoff).count()

    if total_alerts == 0:
        return {"status": "skipped", "reason": "no_alerts"}

    fp_rate = fp_alerts / total_alerts
    current_contamination = float(getattr(settings, "ML_CONTAMINATION_RATE", 0.05))

    # Ajustement: si trop de FP → réduire le score contamination
    if fp_rate > 0.3:
        new_contamination = max(0.01, current_contamination * 0.8)
        logger.info(
            "Feedback ML: taux FP élevé (%.1f%%) → contamination ajustée de %.3f à %.3f",
            fp_rate * 100, current_contamination, new_contamination,
        )
        train_isolation_forest.delay(days_of_data=30, contamination=new_contamination)
        return {"status": "triggered_retraining", "fp_rate": fp_rate, "new_contamination": new_contamination}

    logger.info("Feedback ML: taux FP acceptable (%.1f%%) — pas de réentraînement", fp_rate * 100)
    return {"status": "ok", "fp_rate": fp_rate}


@shared_task(name="apps.ml.tasks.compute_user_risk_scores")
def compute_user_risk_scores():
    """
    Calcule un score de risque agrégé par utilisateur basé sur:
    - Anomalies ML détectées (×40%)
    - Hits de corrélation (×30%)
    - Menaces CTI (×20%)
    - Échecs d'authentification (×10%)
    Tourne toutes les heures.
    """
    from apps.alerts.models import Alert
    from apps.logs.models import NormalizedLog
    from apps.ml.models import Prediction

    cutoff = timezone.now() - timedelta(hours=24)

    users_with_activity = (
        NormalizedLog.objects.filter(indexed_at__gte=cutoff)
        .exclude(user_email="")
        .exclude(user_email__isnull=True)
        .values_list("user_email", flat=True)
        .distinct()
    )

    risk_scores = []
    for email in users_with_activity:
        user_logs = NormalizedLog.objects.filter(user_email=email, indexed_at__gte=cutoff)

        ml_anomalies = Prediction.objects.filter(
            log__in=user_logs, is_anomaly=True, predicted_at__gte=cutoff
        ).count()

        correlation_hits = Alert.objects.filter(
            source_logs__in=user_logs, created_at__gte=cutoff
        ).distinct().count()

        failed_logins = user_logs.filter(outcome="failure").count()

        cti_threats = 0
        try:
            from apps.threat_intel.models import EnrichedLog
            cti_threats = EnrichedLog.objects.filter(
                log__in=user_logs, is_threat=True
            ).count()
        except Exception:
            pass

        raw_score = (
            ml_anomalies * 40
            + correlation_hits * 30
            + cti_threats * 20
            + min(failed_logins * 2, 100) * 0.1
        )
        normalized_score = min(round(raw_score, 1), 100.0)

        risk_scores.append({
            "user_email": email,
            "risk_score": normalized_score,
            "ml_anomalies": ml_anomalies,
            "correlation_hits": correlation_hits,
            "cti_threats": cti_threats,
            "failed_logins": failed_logins,
        })

    risk_scores.sort(key=lambda x: x["risk_score"], reverse=True)
    logger.info("Scores de risque calculés pour %d utilisateurs", len(risk_scores))
    return {"status": "success", "users_scored": len(risk_scores), "top_risks": risk_scores[:5]}
