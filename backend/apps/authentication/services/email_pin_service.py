"""
Service d'envoi du code PIN de vérification pour la liaison de compte OAuth.
"""
import logging
import random
import string

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

logger = logging.getLogger(__name__)

PROVIDER_NAMES = {
    "google":    "Google",
    "microsoft": "Microsoft",
    "github":    "GitHub",
}

PROVIDER_COLORS = {
    "google":    "#EA4335",
    "microsoft": "#0078D4",
    "github":    "#6e40c9",
}

PROVIDER_LOGOS = {
    "google":    "G",
    "microsoft": "M",
    "github":    "GH",
}


def generate_pin() -> str:
    return "".join(random.choices(string.digits, k=4))


def send_pin_email(
    *,
    to_email: str,
    provider: str,
    provider_display_name: str,
    logplus_user_email: str,
    pin: str,
) -> bool:
    provider_name   = PROVIDER_NAMES.get(provider, provider.capitalize())
    provider_color  = PROVIDER_COLORS.get(provider, "#6366f1")
    provider_letter = PROVIDER_LOGOS.get(provider, provider[0].upper())
    expiry_minutes  = 5

    subject = f"[Log+] Code de vérification — {provider_name}"

    text_body = (
        f"Code de vérification Log+\n\n"
        f"Vous avez demandé de lier votre compte {provider_name} "
        f"({to_email}) à votre compte Log+ ({logplus_user_email}).\n\n"
        f"Votre code : {pin}\n\n"
        f"Ce code est valable {expiry_minutes} minutes.\n\n"
        f"Si vous n'avez pas effectué cette action, ignorez cet email — "
        f"aucune liaison ne sera créée.\n\n"
        f"— Log+"
    )

    html_body = _build_html(
        provider_name=provider_name,
        provider_color=provider_color,
        provider_letter=provider_letter,
        provider_display_name=provider_display_name,
        provider_email=to_email,
        logplus_user_email=logplus_user_email,
        pin=pin,
        expiry_minutes=expiry_minutes,
    )

    from_email = getattr(
        settings, "DEFAULT_FROM_EMAIL", "Log+ <noreply@logplus.ci>"
    )

    try:
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        logger.info("PIN email sent to %s for %s linking", to_email, provider)
        return True
    except Exception as exc:
        logger.error("Failed to send PIN email to %s: %s", to_email, exc)
        return False


def _build_html(
    *,
    provider_name: str,
    provider_color: str,
    provider_letter: str,
    provider_display_name: str,
    provider_email: str,
    logplus_user_email: str,
    pin: str,
    expiry_minutes: int,
) -> str:
    # Build 4 digit boxes — table-cell based for Outlook compatibility
    digit_cells = "".join(
        f"""<td style="padding:0 5px;">
  <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
    <tr>
      <td width="56" height="68" align="center" valign="middle" style="
        width:56px;
        height:68px;
        background:#1a2236;
        border:2px solid {provider_color};
        border-radius:12px;
        font-family:'Courier New',Courier,monospace;
        font-size:38px;
        font-weight:900;
        color:#ffffff;
        text-align:center;
        vertical-align:middle;
        letter-spacing:0;
        box-shadow:0 4px 20px {provider_color}44;
      ">{d}</td>
    </tr>
  </table>
</td>"""
        for d in list(pin)
    )

    year = timezone.now().year

    return f"""<!DOCTYPE html>
<html lang="fr" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Code de v&#233;rification — Log+</title>
  <!--[if mso]>
  <noscript>
    <xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
  </noscript>
  <![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#070d1a;font-family:'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

<!-- Preheader (hidden) -->
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
  Code de v&#233;rification {provider_name} : {pin} — valable {expiry_minutes} minutes. Log+.
</div>

<!-- Outer wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#070d1a;padding:40px 16px;">
  <tr>
    <td align="center">

      <!-- Card -->
      <table width="560" cellpadding="0" cellspacing="0" border="0" style="
        max-width:560px;
        width:100%;
        background-color:#0d1526;
        border-radius:20px;
        border:1px solid #1e2d4a;
        overflow:hidden;
      ">

        <!-- ── TOP BAND ───────────────────────────────────────────── -->
        <tr>
          <td style="
            background:linear-gradient(160deg,{provider_color}1a 0%,#0d1526 55%);
            border-bottom:1px solid #1e2d4a;
            padding:28px 32px 24px;
          ">

            <!-- Brand row -->
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr>
                <!-- S logo -->
                <td width="36" valign="middle">
                  <table cellpadding="0" cellspacing="0" border="0">
                    <tr>
                      <td width="36" height="36" align="center" valign="middle" style="
                        width:36px;height:36px;
                        background:linear-gradient(135deg,#6366f1,#8b5cf6);
                        border-radius:9px;
                        font-family:'Courier New',Courier,monospace;
                        font-size:15px;font-weight:900;
                        color:#ffffff;
                        text-align:center;vertical-align:middle;
                      ">S</td>
                    </tr>
                  </table>
                </td>
                <!-- Brand name -->
                <td valign="middle" style="padding-left:10px;">
                  <span style="font-size:14px;font-weight:700;color:#e2e8f0;letter-spacing:-0.3px;">
                    Log+
                  </span>
                </td>
              </tr>
            </table>

            <!-- Provider badge -->
            <table cellpadding="0" cellspacing="0" border="0" style="margin-top:20px;">
              <tr>
                <td style="
                  background:{provider_color}18;
                  border:1px solid {provider_color}44;
                  border-radius:10px;
                  padding:10px 14px;
                ">
                  <table cellpadding="0" cellspacing="0" border="0">
                    <tr>
                      <!-- Provider letter badge -->
                      <td width="32" height="32" align="center" valign="middle" style="
                        width:32px;height:32px;
                        background:{provider_color};
                        border-radius:8px;
                        font-family:'Courier New',Courier,monospace;
                        font-size:13px;font-weight:900;
                        color:#ffffff;
                        text-align:center;vertical-align:middle;
                      ">{provider_letter}</td>
                      <!-- Provider info -->
                      <td style="padding-left:10px;">
                        <div style="font-size:13px;font-weight:700;color:{provider_color};line-height:1.2;">
                          {provider_name}
                        </div>
                        <div style="font-size:11px;color:#94a3b8;margin-top:2px;line-height:1.2;">
                          {provider_display_name}
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- ── BODY ──────────────────────────────────────────────── -->
        <tr>
          <td style="padding:32px 32px 28px;">

            <!-- Title -->
            <h1 style="
              margin:0 0 10px;
              font-size:22px;font-weight:800;
              color:#f1f5f9;letter-spacing:-0.5px;
              line-height:1.25;
            ">V&#233;rifiez votre compte {provider_name}</h1>

            <!-- Subtitle -->
            <p style="
              margin:0 0 28px;
              font-size:14px;color:#94a3b8;line-height:1.65;
            ">
              Une demande de liaison du compte
              <strong style="color:#e2e8f0;">&nbsp;{provider_email}&nbsp;</strong>
              &#224; votre espace Log+
              (<span style="font-family:'Courier New',Courier,monospace;font-size:12px;color:#64748b;">{logplus_user_email}</span>)
              a &#233;t&#233; initialis&#233;e.
            </p>

            <!-- ── PIN BLOCK ───────────────────────── -->
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="
              background:#111a2e;
              border:1px solid #1e2d4a;
              border-radius:16px;
              margin-bottom:24px;
            ">
              <tr>
                <td style="padding:28px 24px;">

                  <!-- Label -->
                  <p style="
                    margin:0 0 20px;
                    font-size:11px;font-weight:700;
                    color:#475569;letter-spacing:0.12em;
                    text-transform:uppercase;
                    text-align:center;
                  ">Votre code de v&#233;rification</p>

                  <!-- Digit boxes -->
                  <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto 20px;">
                    <tr>{digit_cells}</tr>
                  </table>

                  <!-- Divider -->
                  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:18px;">
                    <tr>
                      <td style="border-bottom:1px solid #1e2d4a;font-size:0;">&nbsp;</td>
                    </tr>
                  </table>

                  <!-- Expiry pill -->
                  <table cellpadding="0" cellspacing="0" border="0" align="center">
                    <tr>
                      <td style="
                        background:{provider_color}18;
                        border:1px solid {provider_color}33;
                        border-radius:20px;
                        padding:6px 18px;
                        font-size:12px;font-weight:700;
                        color:{provider_color};
                        text-align:center;
                      ">
                        &#9201;&nbsp; Valable <strong>{expiry_minutes}&nbsp;minutes</strong>
                      </td>
                    </tr>
                  </table>

                  <!-- Instruction -->
                  <p style="
                    margin:16px 0 0;
                    font-size:12px;color:#475569;
                    text-align:center;line-height:1.5;
                  ">
                    Entrez ce code dans la fen&#234;tre encore ouverte dans votre navigateur.
                  </p>

                </td>
              </tr>
            </table>

            <!-- ── INFO BOX ────────────────────────── -->
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr>
                <td style="
                  background:#0d1e38;
                  border:1px solid #1e3a5f;
                  border-left:3px solid #3b82f6;
                  border-radius:0 10px 10px 0;
                  padding:14px 16px;
                ">
                  <p style="margin:0 0 5px;font-size:12px;font-weight:700;color:#93c5fd;">
                    &#8505;&#65039;&nbsp; Pourquoi ce code&#160;?
                  </p>
                  <p style="margin:0;font-size:12px;color:#64748b;line-height:1.6;">
                    Ce code confirme que vous poss&#233;dez bien ce compte {provider_name}.
                    Une fois li&#233;, Log+ surveillera les connexions inhabituelles
                    (nouvelle localisation, nouvel appareil, brute-force) et vous alertera.
                  </p>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- ── WARNING STRIP ──────────────────────────────────────── -->
        <tr>
          <td style="
            background:#180b0b;
            border-top:1px solid #2d1515;
            padding:14px 32px;
          ">
            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr>
                <td width="18" valign="top" style="font-size:13px;color:#ef4444;line-height:1;">&#9888;</td>
                <td style="padding-left:8px;font-size:12px;color:#6b7280;line-height:1.55;">
                  Si vous n&rsquo;avez pas initialis&#233; cette liaison, ignorez cet email.
                  Aucun compte ne sera li&#233; et aucune action n&rsquo;est requise.
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ── FOOTER ─────────────────────────────────────────────── -->
        <tr>
          <td style="
            background:#070d1a;
            border-top:1px solid #1e2d4a;
            padding:20px 32px;
            text-align:center;
          ">
            <p style="margin:0;font-size:11px;color:#1e2d4a;line-height:1.7;">
              Log+ &middot; Security Information &amp; Event Management<br/>
              Institut des Ing&#233;nieurs Technologiques &middot; {year}
            </p>
          </td>
        </tr>

      </table><!-- /card -->

    </td>
  </tr>
</table><!-- /outer -->

</body>
</html>"""
