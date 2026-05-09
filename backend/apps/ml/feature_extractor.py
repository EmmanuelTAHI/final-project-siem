"""
Extraction des features des NormalizedLog pour le module ML.
Réf. : Islam 2023, Tendikov et al. 2024 — SIEM anomaly detection features.
"""
import hashlib
import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from django.db.models import Count, QuerySet
from django.utils import timezone

logger = logging.getLogger(__name__)

# Constante pour is_new_country : nombre de jours d'historique à analyser
COUNTRY_HISTORY_DAYS = 90


class FeatureExtractor:
    """
    Extrait les vecteurs de features numériques depuis les NormalizedLog
    pour alimenter le modèle Isolation Forest.
    """

    OUTCOME_ENCODING = {
        "success": 0,
        "failure": 1,
        "unknown": 2,
    }

    def __init__(self):
        self.country_encoder: dict[str, int] = {}
        self._country_counter = 0
        self._user_country_history: dict[str, set] = {}

    def fit(self, logs_df: pd.DataFrame) -> "FeatureExtractor":
        """
        Construit les encodages à partir du DataFrame d'entraînement.

        Args:
            logs_df: DataFrame avec les colonnes des NormalizedLog.

        Returns:
            self
        """
        # Encoder les pays
        countries = logs_df["geo_country"].dropna().unique()
        for country in countries:
            if country not in self.country_encoder:
                self.country_encoder[country] = self._country_counter
                self._country_counter += 1

        # Construire l'historique des pays par utilisateur
        for _, row in logs_df.iterrows():
            email = row.get("user_email")
            country = row.get("geo_country")
            if email and country:
                if email not in self._user_country_history:
                    self._user_country_history[email] = set()
                self._user_country_history[email].add(country)

        return self

    def transform(self, logs_queryset: QuerySet) -> tuple[np.ndarray, list]:
        """
        Transforme un QuerySet de NormalizedLog en matrice de features.

        Args:
            logs_queryset: QuerySet de NormalizedLog.

        Returns:
            Tuple (features_matrix, log_ids)
        """
        from apps.logs.models import NormalizedLog

        log_ids = []
        features_list = []

        for log in logs_queryset.iterator(chunk_size=500):
            try:
                features = self._extract_single(log)
                features_list.append(features)
                log_ids.append(str(log.id))
            except Exception as exc:
                logger.warning("Impossible d'extraire features pour log %s : %s", log.id, exc)

        if not features_list:
            return np.array([]).reshape(0, 9), []

        return np.array(features_list, dtype=np.float64), log_ids

    def _extract_single(self, log) -> list[float]:
        """
        Extrait le vecteur de 9 features pour un NormalizedLog.
        Features : hour_of_day, day_of_week, is_weekend, outcome_encoded,
                   country_encoded, failure_count_1h, failure_count_24h,
                   user_agent_hash, is_new_country
        """
        from apps.logs.models import NormalizedLog

        event_time = log.event_time

        # 1. hour_of_day (0-23)
        hour_of_day = float(event_time.hour)

        # 2. day_of_week (0=lundi, 6=dimanche)
        day_of_week = float(event_time.weekday())

        # 3. is_weekend
        is_weekend = 1.0 if event_time.weekday() >= 5 else 0.0

        # 4. outcome_encoded
        outcome_encoded = float(self.OUTCOME_ENCODING.get(log.outcome, 2))

        # 5. country_encoded (LabelEncoder)
        country = log.geo_country or ""
        country_encoded = float(self.country_encoder.get(country, self._country_counter))

        # 6 & 7. failure_count_1h et failure_count_24h
        failure_1h = 0.0
        failure_24h = 0.0
        if log.user_email:
            one_hour_ago = event_time - timedelta(hours=1)
            one_day_ago = event_time - timedelta(hours=24)
            failure_1h = float(
                NormalizedLog.objects.filter(
                    user_email=log.user_email,
                    action="login_failure",
                    event_time__gte=one_hour_ago,
                    event_time__lt=event_time,
                ).count()
            )
            failure_24h = float(
                NormalizedLog.objects.filter(
                    user_email=log.user_email,
                    action="login_failure",
                    event_time__gte=one_day_ago,
                    event_time__lt=event_time,
                ).count()
            )

        # 8. user_agent_hash (MD5 tronqué → int mod 10000)
        ua = log.user_agent or ""
        ua_hash = float(int(hashlib.md5(ua.encode()).hexdigest()[:8], 16) % 10000)

        # 9. is_new_country
        is_new_country = 0.0
        if log.user_email and log.geo_country:
            known_countries = self._user_country_history.get(log.user_email, set())
            if log.geo_country not in known_countries:
                is_new_country = 1.0

        return [
            hour_of_day,
            day_of_week,
            is_weekend,
            outcome_encoded,
            country_encoded,
            failure_1h,
            failure_24h,
            ua_hash,
            is_new_country,
        ]

    def to_dataframe(self, logs_queryset: QuerySet) -> pd.DataFrame:
        """Convertit un QuerySet en DataFrame pour l'entraînement."""
        records = list(
            logs_queryset.values(
                "id",
                "event_time",
                "user_email",
                "outcome",
                "geo_country",
                "action",
                "user_agent",
            )
        )
        return pd.DataFrame(records) if records else pd.DataFrame()
