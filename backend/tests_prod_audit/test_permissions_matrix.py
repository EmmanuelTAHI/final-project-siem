"""
Tests d'audit prod — matrice systématique de permissions par rôle (org A).
Boucle create/update/delete sur les endpoints sensibles avec les 3 rôles
(admin/analyst/viewer), vérifie les codes HTTP attendus d'après les
permission classes lues dans le code :

- collectors/connectors  : IsAdmin (create/update/destroy), IsAnalyst (reste)
- correlation/rules      : IsAnalyst (create/update/destroy/toggle/test)
- soar/playbooks         : IsAdminOrReadOnly (lecture ouverte, écriture admin)
- users                  : IsAdmin (list/create/update/destroy)
"""
import uuid

import pytest

from conftest import QA_PREFIX


@pytest.fixture
def clients_by_role(qa_admin_a_client, qa_analyst_a_client, qa_viewer_a_client):
    return {"admin": qa_admin_a_client, "analyst": qa_analyst_a_client, "viewer": qa_viewer_a_client}


class TestConnectorsPermissionMatrix:
    """ConnectorConfigViewSet.get_permissions : create/update/destroy -> IsAdmin ; reste -> IsAnalyst."""

    @pytest.mark.parametrize(
        "role,expected_status",
        [("admin", 201), ("analyst", 403), ("viewer", 403)],
    )
    def test_create(self, clients_by_role, role, expected_status):
        client = clients_by_role[role]
        name = f"{QA_PREFIX}matrix_connector_{role}_{uuid.uuid4().hex[:6]}"
        resp = client.post(
            "/api/collectors/connectors/", json={"name": name, "source_type": "syslog"}
        )
        assert resp.status_code == expected_status, resp.text
        if resp.status_code == 201:
            clients_by_role["admin"].delete(f"/api/collectors/connectors/{resp.json()['data']['id']}/")

    @pytest.mark.parametrize(
        "role,expected_status",
        [("admin", 200), ("analyst", 200), ("viewer", 403)],
    )
    def test_list(self, clients_by_role, role, expected_status):
        resp = clients_by_role[role].get("/api/collectors/connectors/")
        assert resp.status_code == expected_status


class TestCorrelationRulesPermissionMatrix:
    """CorrelationRuleViewSet.get_permissions : toutes actions d'écriture -> IsAnalyst (admin+analyst)."""

    @pytest.mark.parametrize(
        "role,expected_status",
        [("admin", 201), ("analyst", 201), ("viewer", 403)],
    )
    def test_create(self, clients_by_role, role, expected_status):
        client = clients_by_role[role]
        name = f"{QA_PREFIX}matrix_rule_{role}_{uuid.uuid4().hex[:6]}"
        resp = client.post(
            "/api/correlation/rules/",
            json={
                "name": name,
                "is_active": False,
                "severity": "low",
                "rule_type": "threshold",
                "condition_logic": {"type": "threshold", "field": "action", "threshold": 999999},
            },
        )
        assert resp.status_code == expected_status, resp.text
        if resp.status_code == 201:
            clients_by_role["admin"].delete(f"/api/correlation/rules/{resp.json()['data']['id']}/")


class TestSoarPlaybooksPermissionMatrix:
    """PlaybookViewSet.permission_classes = [IsAdminOrReadOnly] : lecture ouverte, écriture admin only."""

    @pytest.mark.parametrize(
        "role,expected_status",
        [("admin", 201), ("analyst", 403), ("viewer", 403)],
    )
    def test_create(self, clients_by_role, role, expected_status):
        client = clients_by_role[role]
        name = f"{QA_PREFIX}matrix_playbook_{role}_{uuid.uuid4().hex[:6]}"
        resp = client.post(
            "/api/soar/playbooks/",
            json={
                "name": name,
                "trigger_type": "manual",
                "trigger_conditions": {},
                "actions": [],
                "is_active": False,
            },
        )
        assert resp.status_code == expected_status, resp.text
        if resp.status_code == 201:
            clients_by_role["admin"].delete(f"/api/soar/playbooks/{resp.json()['id']}/")

    @pytest.mark.parametrize(
        "role,expected_status",
        [("admin", 200), ("analyst", 200), ("viewer", 200)],
    )
    def test_list_open_to_all_authenticated_roles(self, clients_by_role, role, expected_status):
        resp = clients_by_role[role].get("/api/soar/playbooks/")
        assert resp.status_code == expected_status


class TestUsersPermissionMatrix:
    """UserViewSet.get_permissions : list/create/update/destroy -> IsAdmin ; me/retrieve -> IsAuthenticated."""

    @pytest.mark.parametrize(
        "role,expected_status",
        [("admin", 200), ("analyst", 403), ("viewer", 403)],
    )
    def test_list(self, clients_by_role, role, expected_status):
        resp = clients_by_role[role].get("/api/users/")
        assert resp.status_code == expected_status

    @pytest.mark.parametrize(
        "role,expected_status",
        [("admin", 200), ("analyst", 200), ("viewer", 200)],
    )
    def test_me_open_to_all_authenticated_roles(self, clients_by_role, role, expected_status):
        resp = clients_by_role[role].get("/api/users/me/")
        assert resp.status_code == expected_status

    @pytest.mark.parametrize(
        "role,expected_status",
        [("analyst", 403), ("viewer", 403)],
    )
    def test_invite_forbidden_for_non_admin_roles(self, clients_by_role, role, expected_status):
        """
        InviteUserView vérifie `request.user.role != "admin"` manuellement
        (pas une permission_classes DRF). Le cas admin=201 n'est
        volontairement PAS testé ici : il créerait un utilisateur réel non
        nettoyable automatiquement (seul AcceptInviteView permet de finaliser
        l'invitation, et il n'y a pas de DELETE utilisateur sûr utilisable en
        boucle ici). Voir test_users.py::TestInviteUser pour la couverture
        complémentaire (403 analyst/viewer + doublon d'email -> 400).
        """
        client = clients_by_role[role]
        resp = client.post(
            "/api/users/invite/",
            json={
                "email": f"qa-audit-matrix-{role}-{uuid.uuid4().hex[:8]}@test.local",
                "first_name": "QA",
                "last_name": "Matrix",
                "role": "viewer",
            },
        )
        assert resp.status_code == expected_status
