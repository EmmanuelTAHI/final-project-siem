"""
Générateur de rapports PDF de conformité — base commune.
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BLUE = colors.HexColor("#1e40af")
DARK = colors.HexColor("#0f172a")
GRAY = colors.HexColor("#94a3b8")
RED = colors.HexColor("#dc2626")
GREEN = colors.HexColor("#16a34a")
ORANGE = colors.HexColor("#d97706")
LIGHT_BG = colors.HexColor("#f1f5f9")


def build_styles():
    styles = getSampleStyleSheet()
    custom = {
        "Title": ParagraphStyle("Title", fontSize=24, textColor=BLUE, alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica-Bold"),
        "Subtitle": ParagraphStyle("Subtitle", fontSize=12, textColor=GRAY, alignment=TA_CENTER, spaceAfter=20),
        "H2": ParagraphStyle("H2", fontSize=14, textColor=DARK, fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=6),
        "H3": ParagraphStyle("H3", fontSize=11, textColor=BLUE, fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=4),
        "Body": ParagraphStyle("Body", fontSize=9, textColor=DARK, leading=14, spaceAfter=4),
        "Meta": ParagraphStyle("Meta", fontSize=8, textColor=GRAY, alignment=TA_CENTER),
        "Pass": ParagraphStyle("Pass", fontSize=9, textColor=GREEN, fontName="Helvetica-Bold"),
        "Fail": ParagraphStyle("Fail", fontSize=9, textColor=RED, fontName="Helvetica-Bold"),
        "Warn": ParagraphStyle("Warn", fontSize=9, textColor=ORANGE, fontName="Helvetica-Bold"),
    }
    return {**{k: styles[k] for k in styles.byName}, **custom}


def status_style(styles, value: str):
    v = value.lower()
    if v in ("conforme", "pass", "✓", "oui", "yes", "ok"):
        return styles["Pass"]
    if v in ("non conforme", "fail", "✗", "non", "no"):
        return styles["Fail"]
    return styles["Warn"]


def make_table(data: list[list], col_widths=None, header_bg=BLUE):
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(style)
    return t


class BaseReportGenerator:
    FRAMEWORK = "BASE"
    TITLE = "Rapport de conformité"

    def __init__(self, period_days: int = 30):
        self.period_days = period_days
        self.styles = build_styles()
        self.generated_at = datetime.utcnow()

    def collect_data(self) -> dict:
        raise NotImplementedError

    def build_elements(self, data: dict) -> list:
        raise NotImplementedError

    def generate(self) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            title=f"{self.FRAMEWORK} Compliance Report",
            author="Log+",
        )

        data = self.collect_data()
        elements = self._build_header() + self.build_elements(data) + self._build_footer()

        doc.build(elements)
        return buffer.getvalue()

    def _build_header(self) -> list:
        s = self.styles
        return [
            Paragraph("Log+", s["Title"]),
            Paragraph(self.TITLE, s["Subtitle"]),
            Paragraph(
                f"Période : {self.period_days} derniers jours | Généré le : "
                f"{self.generated_at.strftime('%d/%m/%Y à %H:%M UTC')}",
                s["Meta"],
            ),
            HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=16),
        ]

    def _build_footer(self) -> list:
        return [
            Spacer(1, 20),
            HRFlowable(width="100%", thickness=0.5, color=GRAY),
            Paragraph(
                f"Ce rapport a été généré automatiquement par Log+ — "
                f"TAHI Ezan Franck Emmanuel — {self.generated_at.year}",
                self.styles["Meta"],
            ),
        ]
