"""
Charte email partagée pour tous les messages sortants de Log+.
Structure HTML "table-based" compatible Outlook/Gmail (MSO conditionals,
preheader caché, boîtes de code en table cells) — même qualité de rendu
partout, un seul endroit à maintenir pour la charte visuelle.
Palette alignée sur le thème sombre de la plateforme (voir frontend globals).
"""
from django.utils import timezone

BG = "#070d1a"
CARD = "#0d1526"
BORDER = "#1e2d4a"
TEXT = "#f1f5f9"
TEXT_DIM = "#94a3b8"
TEXT_FAINT = "#64748b"
MUTED = "#475569"

PRIMARY = "#3B82F6"
SECONDARY = "#06D6A0"
WARNING = "#F59E0B"
DANGER = "#EF4444"

LEVEL_COLORS = {"info": PRIMARY, "warning": WARNING, "critical": DANGER, "success": SECONDARY}


def _brand_header() -> str:
    return f"""
        <table cellpadding="0" cellspacing="0" border="0" width="100%">
          <tr>
            <td width="36" valign="middle">
              <table cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="36" height="36" align="center" valign="middle" style="
                    width:36px;height:36px;
                    background:linear-gradient(135deg,{PRIMARY},{SECONDARY});
                    border-radius:10px;
                    font-family:'Segoe UI',Helvetica,Arial,sans-serif;
                    font-size:16px;font-weight:900;
                    color:#ffffff;
                    text-align:center;vertical-align:middle;
                  ">L+</td>
                </tr>
              </table>
            </td>
            <td valign="middle" style="padding-left:10px;">
              <span style="font-size:14px;font-weight:700;color:#e2e8f0;letter-spacing:-0.3px;">
                Log+
              </span>
              <div style="font-size:10.5px;color:{TEXT_FAINT};letter-spacing:0.06em;text-transform:uppercase;margin-top:1px;">
                Security Operations Center
              </div>
            </td>
          </tr>
        </table>"""


def digit_boxes(code: str, accent: str) -> str:
    """Boîtes monospace pour un code numérique (OTP / PIN), une <td> par chiffre."""
    cells = "".join(
        f"""<td style="padding:0 5px;">
  <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    <tr>
      <td width="50" height="62" align="center" valign="middle" style="
        width:50px;
        height:62px;
        background:#1a2236;
        border:2px solid {accent};
        border-radius:12px;
        font-family:'Courier New',Courier,monospace;
        font-size:32px;
        font-weight:900;
        color:#ffffff;
        text-align:center;
        vertical-align:middle;
        box-shadow:0 4px 20px {accent}33;
      ">{d}</td>
    </tr>
  </table>
</td>"""
        for d in code
    )
    return f"""<table cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto;"><tr>{cells}</tr></table>"""


def cta_button(label: str, href: str, color: str = PRIMARY) -> str:
    return f"""
        <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin:4px auto;">
          <tr>
            <td style="border-radius:10px;background:{color};">
              <a href="{href}" style="
                display:inline-block;
                padding:12px 28px;
                font-size:14px;font-weight:700;
                color:#ffffff;text-decoration:none;
                border-radius:10px;
              ">{label}</a>
            </td>
          </tr>
        </table>"""


def info_row(label: str, value: str, mono: bool = False) -> str:
    family = "'Courier New',Courier,monospace" if mono else "inherit"
    return f"""
              <tr>
                <td style="padding:6px 0;font-size:12.5px;color:{TEXT_FAINT};width:110px;vertical-align:top;">{label}</td>
                <td style="padding:6px 0;font-size:12.5px;color:{TEXT_DIM};font-family:{family};">{value}</td>
              </tr>"""


def metadata_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(info_row(k, v) for k, v in rows)
    return f"""
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="
              background:#111a2e;border:1px solid {BORDER};border-radius:12px;margin:20px 0;
            ">
              <tr><td style="padding:16px 18px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">{body}</table>
              </td></tr>
            </table>"""


def render_email(
    *,
    preheader: str,
    badge_label: str,
    badge_letter: str,
    accent: str,
    title: str,
    subtitle_html: str,
    body_html: str,
    warning_html: str = "",
    footer_extra: str = "",
) -> str:
    """
    Enveloppe HTML complète (Outlook-safe, dark theme Log+).
    `body_html` est injecté tel quel entre le sous-titre et le bandeau d'avertissement.
    """
    year = timezone.now().year
    warning_block = ""
    if warning_html:
        warning_block = f"""
        <tr>
          <td style="background:#180b0b;border-top:1px solid #2d1515;padding:14px 32px;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr>
                <td width="18" valign="top" style="font-size:13px;color:{DANGER};line-height:1;">&#9888;</td>
                <td style="padding-left:8px;font-size:12px;color:{TEXT_FAINT};line-height:1.55;">{warning_html}</td>
              </tr>
            </table>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta name="color-scheme" content="dark light" />
  <meta name="supported-color-schemes" content="dark light" />
  <title>{title} — Log+</title>
  <!--[if mso]>
  <noscript>
    <xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
  </noscript>
  <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:{BG};font-family:'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}</div>

<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{BG};padding:40px 16px;">
  <tr>
    <td align="center">

      <table width="560" cellpadding="0" cellspacing="0" border="0" style="
        max-width:560px;width:100%;background-color:{CARD};
        border-radius:20px;border:1px solid {BORDER};overflow:hidden;
      ">

        <!-- TOP BAND -->
        <tr>
          <td style="
            background:linear-gradient(160deg,{accent}1a 0%,{CARD} 55%);
            border-bottom:1px solid {BORDER};
            padding:26px 32px 22px;
          ">
            {_brand_header()}

            <table cellpadding="0" cellspacing="0" border="0" style="margin-top:20px;">
              <tr>
                <td style="background:{accent}18;border:1px solid {accent}44;border-radius:10px;padding:9px 14px;">
                  <table cellpadding="0" cellspacing="0" border="0">
                    <tr>
                      <td width="30" height="30" align="center" valign="middle" style="
                        width:30px;height:30px;background:{accent};border-radius:8px;
                        font-family:'Courier New',Courier,monospace;font-size:12px;font-weight:900;
                        color:#ffffff;text-align:center;vertical-align:middle;
                      ">{badge_letter}</td>
                      <td style="padding-left:10px;">
                        <div style="font-size:12.5px;font-weight:700;color:{accent};line-height:1.2;">{badge_label}</div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- BODY -->
        <tr>
          <td style="padding:30px 32px 26px;">
            <h1 style="margin:0 0 10px;font-size:22px;font-weight:800;color:{TEXT};letter-spacing:-0.5px;line-height:1.25;">{title}</h1>
            <p style="margin:0 0 22px;font-size:14px;color:{TEXT_DIM};line-height:1.65;">{subtitle_html}</p>
            {body_html}
          </td>
        </tr>
{warning_block}

        <!-- FOOTER -->
        <tr>
          <td style="background:{BG};border-top:1px solid {BORDER};padding:20px 32px;text-align:center;">
            {footer_extra}
            <p style="margin:0;font-size:11px;color:{BORDER};line-height:1.7;">
              Log+ &middot; Security Information &amp; Event Management<br/>
              Institut des Ing&#233;nieurs Technologiques &middot; {year}
            </p>
          </td>
        </tr>

      </table>

    </td>
  </tr>
</table>

</body>
</html>"""
