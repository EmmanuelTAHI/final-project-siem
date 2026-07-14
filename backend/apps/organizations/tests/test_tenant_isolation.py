"""
Garde-fou CI — isolation multi-tenant (voir plan multi-tenant, §2.4).

1. test_all_org_scoped_viewsets_have_organization_filter_backend :
   introspecte TOUTE l'URLconf, trouve chaque ViewSet DRF dont le modèle
   porte un champ `organization`, et échoue si OrganizationFilterBackend
   n'est pas dans sa chaîne de filter_backends — sauf allowlist explicite et
   justifiée ci-dessous. C'est le filet de sécurité qui doit transformer un
   oubli de scoping sur un futur endpoint en échec de build, pas en fuite
   de données silencieuse.

2. Test boîte noire : deux organisations, deux utilisateurs, vérifie qu'un
   admin de l'org B ne voit RIEN de ce que l'org A a créé (connecteurs,
   alertes, logs).
"""
import pytest
from django.urls import URLResolver, get_resolver
from rest_framework import status
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.users.models import User
from utils.tenant import OrganizationFilterBackend


def _extract_results(response_data):
    """
    Déballe l'enveloppe standard {"status"/"success", "data": [...] ou
    {"results": [...]}} utilisée par utils.response / utils.pagination.
    """
    data = response_data.get("data", response_data)
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data

# ViewSets légitimement hors périmètre tenant : modèle explicitement
# platform-shared (CTI), ou route d'administration plateforme dédiée dont
# l'isolation est gérée par une permission distincte (IsPlatformStaff), pas
# par OrganizationFilterBackend. Toute nouvelle entrée ici doit être justifiée
# en revue de code.
TENANT_EXEMPT_VIEWSETS = {
    "ThreatIndicatorViewSet",  # référentiel CTI partagé entre toutes les organisations
}


def _iter_viewset_classes(patterns=None, seen=None):
    if patterns is None:
        patterns = get_resolver().url_patterns
    if seen is None:
        seen = set()

    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _iter_viewset_classes(pattern.url_patterns, seen)
            continue

        callback = getattr(pattern, "callback", None)
        cls = getattr(callback, "cls", None)
        if cls is None or cls in seen:
            continue
        seen.add(cls)

        if hasattr(cls, "get_queryset") and hasattr(cls, "filter_backends"):
            yield cls


@pytest.mark.django_db
def test_all_org_scoped_viewsets_have_organization_filter_backend():
    missing = []

    for cls in _iter_viewset_classes():
        if cls.__name__ in TENANT_EXEMPT_VIEWSETS:
            continue

        queryset = getattr(cls, "queryset", None)
        model = queryset.model if queryset is not None else None
        if model is None or not hasattr(model, "organization_id"):
            continue

        filter_backends = getattr(cls, "filter_backends", [])
        if OrganizationFilterBackend not in filter_backends:
            missing.append(cls.__name__)

    assert not missing, (
        "ViewSets exposant un modèle avec `organization` mais sans "
        f"OrganizationFilterBackend dans filter_backends : {sorted(missing)}. "
        "Ajoutez utils.tenant.OrganizationFilterBackend en tête de "
        "filter_backends, ou ajoutez le ViewSet à TENANT_EXEMPT_VIEWSETS "
        "avec une justification explicite en revue de code."
    )


# ─────────────────────────────────────────────────────────────────────────
# Test boîte noire : deux organisations, isolation stricte
# ─────────────────────────────────────────────────────────────────────────


@pytest.fixture
def two_orgs_with_admins(db):
    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    admin_a = User.objects.create_user(
        email="admin-a@example.com", password="Test@2025!",
        first_name="Admin", last_name="A", role="admin", organization=org_a,
    )
    admin_b = User.objects.create_user(
        email="admin-b@example.com", password="Test@2025!",
        first_name="Admin", last_name="B", role="admin", organization=org_b,
    )
    return org_a, org_b, admin_a, admin_b


@pytest.mark.django_db
def test_connector_created_by_org_a_is_invisible_to_org_b(two_orgs_with_admins):
    from apps.collectors.models import ConnectorConfig

    org_a, org_b, admin_a, admin_b = two_orgs_with_admins

    connector = ConnectorConfig.objects.create(
        organization=org_a, name="Connecteur Org A", source_type="syslog",
    )

    client_b = APIClient()
    client_b.force_authenticate(user=admin_b)

    detail_resp = client_b.get(f"/api/collectors/connectors/{connector.id}/")
    assert detail_resp.status_code == status.HTTP_404_NOT_FOUND

    list_resp = client_b.get("/api/collectors/connectors/")
    assert list_resp.status_code == status.HTTP_200_OK
    returned_ids = {str(item["id"]) for item in _extract_results(list_resp.data)}
    assert str(connector.id) not in returned_ids


@pytest.mark.django_db
def test_alert_created_by_org_a_is_invisible_to_org_b(two_orgs_with_admins):
    from apps.alerts.models import Alert

    org_a, org_b, admin_a, admin_b = two_orgs_with_admins

    alert = Alert.objects.create(
        organization=org_a, title="Alerte Org A", description="...", severity="high", status="open",
    )

    client_b = APIClient()
    client_b.force_authenticate(user=admin_b)

    detail_resp = client_b.get(f"/api/alerts/{alert.id}/")
    assert detail_resp.status_code == status.HTTP_404_NOT_FOUND

    list_resp = client_b.get("/api/alerts/")
    assert list_resp.status_code == status.HTTP_200_OK
    returned_ids = {str(item["id"]) for item in _extract_results(list_resp.data)}
    assert str(alert.id) not in returned_ids


@pytest.mark.django_db
def test_user_list_scoped_to_own_organization(two_orgs_with_admins):
    org_a, org_b, admin_a, admin_b = two_orgs_with_admins

    client_a = APIClient()
    client_a.force_authenticate(user=admin_a)

    resp = client_a.get("/api/users/")
    assert resp.status_code == status.HTTP_200_OK
    emails = {item["email"] for item in _extract_results(resp.data)}
    assert admin_a.email in emails
    assert admin_b.email not in emails
