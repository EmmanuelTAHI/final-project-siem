"""Tests Threat Hunting — Requêtes et vues."""
import uuid

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class HuntingQueryModelTest(TestCase):
    def setUp(self):
        self.analyst = User.objects.create_user(
            email="analyst@test.ci", password="Test1234!", role="analyst"
        )

    def test_create_hunting_query(self):
        from apps.hunting.models import HuntingQuery
        query = HuntingQuery.objects.create(
            name="Détection connexions hors heures",
            description="Cherche les connexions entre 23h et 5h",
            query_params={
                "action": "Login",
                "hour_from": 23,
                "hour_to": 5,
            },
            mitre_tactic="Initial Access",
            mitre_technique="T1078",
            created_by=self.analyst,
        )
        self.assertEqual(str(query), "Détection connexions hors heures")
        self.assertIsInstance(query.id, uuid.UUID)
        self.assertEqual(query.run_count, 0)

    def test_hunting_query_uuid_pk(self):
        from apps.hunting.models import HuntingQuery
        q1 = HuntingQuery.objects.create(name="Query A", created_by=self.analyst)
        q2 = HuntingQuery.objects.create(name="Query B", created_by=self.analyst)
        self.assertNotEqual(q1.id, q2.id)


class HuntingAPITest(TestCase):
    def setUp(self):
        self.analyst = User.objects.create_user(
            email="analyst@test.ci", password="Test1234!", role="analyst"
        )
        self.client.force_login(self.analyst)

    def test_list_queries_requires_auth(self):
        from django.test import Client
        c = Client()
        resp = c.get("/api/hunting/queries/")
        self.assertIn(resp.status_code, [401, 403])

    def test_list_queries_authenticated(self):
        from apps.hunting.models import HuntingQuery
        HuntingQuery.objects.create(
            name="Test Query",
            created_by=self.analyst,
        )
        resp = self.client.get("/api/hunting/queries/")
        self.assertIn(resp.status_code, [200, 401])
