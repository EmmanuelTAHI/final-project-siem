"""Tests Rapports de conformité PDF."""
from unittest.mock import patch, MagicMock

from django.test import TestCase


class ReportGeneratorTest(TestCase):
    def _mock_db(self):
        """Mock les queryset Django pour éviter les dépendances base de données."""
        return MagicMock(
            count=MagicMock(return_value=0),
            filter=MagicMock(return_value=MagicMock(count=MagicMock(return_value=0))),
            exclude=MagicMock(return_value=MagicMock(count=MagicMock(return_value=0))),
            values=MagicMock(return_value=MagicMock(
                distinct=MagicMock(return_value=MagicMock(count=MagicMock(return_value=0)))
            )),
        )

    @patch("apps.reports.generators.gdpr.NormalizedLog")
    @patch("apps.reports.generators.gdpr.Alert")
    @patch("apps.reports.generators.gdpr.AuditTrail")
    def test_gdpr_generate_returns_bytes(self, mock_audit, mock_alert, mock_log):
        for m in (mock_audit, mock_alert, mock_log):
            qs = MagicMock()
            qs.count.return_value = 0
            qs.filter.return_value = qs
            qs.exclude.return_value = qs
            qs.values.return_value = qs
            qs.distinct.return_value = qs
            m.objects.filter.return_value = qs
            m.objects.count.return_value = 0

        from apps.reports.generators.gdpr import GDPRReportGenerator
        gen = GDPRReportGenerator(period_days=7)
        pdf = gen.generate()
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))

    @patch("apps.reports.generators.pci_dss.NormalizedLog")
    @patch("apps.reports.generators.pci_dss.Alert")
    @patch("apps.reports.generators.pci_dss.AuditTrail")
    def test_pci_dss_generate_returns_bytes(self, mock_audit, mock_alert, mock_log):
        for m in (mock_audit, mock_alert, mock_log):
            qs = MagicMock()
            qs.count.return_value = 0
            qs.filter.return_value = qs
            qs.exclude.return_value = qs
            qs.values.return_value = qs
            qs.distinct.return_value = qs
            m.objects.filter.return_value = qs
            m.objects.count.return_value = 0

        from apps.reports.generators.pci_dss import PCIDSSReportGenerator
        gen = PCIDSSReportGenerator(period_days=7)
        pdf = gen.generate()
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))

    @patch("apps.reports.generators.iso27001.NormalizedLog")
    @patch("apps.reports.generators.iso27001.Alert")
    @patch("apps.reports.generators.iso27001.AuditTrail")
    @patch("apps.reports.generators.iso27001.CorrelationRule")
    @patch("apps.reports.generators.iso27001.User")
    def test_iso27001_generate_returns_bytes(self, mock_user, mock_rule, mock_audit, mock_alert, mock_log):
        for m in (mock_audit, mock_alert, mock_log, mock_rule, mock_user):
            qs = MagicMock()
            qs.count.return_value = 0
            qs.filter.return_value = qs
            qs.exists.return_value = False
            qs.values.return_value = qs
            qs.distinct.return_value = qs
            m.objects.filter.return_value = qs
            m.objects.count.return_value = 0

        from apps.reports.generators.iso27001 import ISO27001ReportGenerator
        gen = ISO27001ReportGenerator(period_days=7)
        pdf = gen.generate()
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))
