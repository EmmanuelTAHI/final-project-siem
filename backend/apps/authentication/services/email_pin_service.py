"""
Service d'envoi du code PIN de vérification pour la liaison de compte OAuth.
"""
import logging
import random
import string

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

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
    argus_user_email: str,
    pin: str,
) -> bool:
    provider_name   = PROVIDER_NAMES.get(provider, provider.capitalize())
    provider_color  = PROVIDER_COLORS.get(provider, "#6366f1")
    provider_letter = PROVIDER_LOGOS.get(provider, provider[0].upper())
    expiry_minutes  = 5

    subject = f"[Argus] Code de vérification — {provider_name}"

    text_body = (
        f"Code de vérification Argus\n\n"
        f"Vous avez demandé de lier votre compte {provider_name} "
        f"({to_email}) à votre compte Argus ({argus_user_email}).\n\n"
        f"Votre code : {pin}\n\n"
        f"Ce code est valable {expiry_minutes} minutes.\n\n"
        f"Si vous n'avez pas effectué cette action, ignorez cet email — "
        f"aucune liaison ne sera créée.\n\n"
        f"— Argus"
    )

    html_body = _build_html(
        provider_name=provider_name,
        provider_color=provider_color,
        provider_letter=provider_letter,
        provider_display_name=provider_display_name,
        provider_email=to_email,
        argus_user_email=argus_user_email,
        pin=pin,
        expiry_minutes=expiry_minutes,
    )

    from_email = getattr(
        settings, "DEFAULT_FROM_EMAIL", "Argus <noreply@argussiem.com>"
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
    argus_user_email: str,
    pin: str,
    expiry_minutes: int,
) -> str:
    from . import email_theme as t

    body = f"""
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="
              background:#111a2e;border:1px solid {t.BORDER};border-radius:16px;margin-bottom:24px;
            ">
              <tr><td style="padding:28px 24px;">
                <p style="margin:0 0 20px;font-size:11px;font-weight:700;color:{t.MUTED};
                   letter-spacing:0.12em;text-transform:uppercase;text-align:center;">
                  Votre code de v&#233;rification
                </p>
                {t.digit_boxes(pin, provider_color)}
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:18px 0;">
                  <tr><td style="border-bottom:1px solid {t.BORDER};font-size:0;">&nbsp;</td></tr>
                </table>
                <table cellpadding="0" cellspacing="0" border="0" align="center">
                  <tr><td style="background:{provider_color}18;border:1px solid {provider_color}33;
                    border-radius:20px;padding:6px 18px;font-size:12px;font-weight:700;
                    color:{provider_color};text-align:center;">
                    &#9201;&nbsp; Valable <strong>{expiry_minutes}&nbsp;minutes</strong>
                  </td></tr>
                </table>
                <p style="margin:16px 0 0;font-size:12px;color:{t.MUTED};text-align:center;line-height:1.5;">
                  Entrez ce code dans la fen&#234;tre encore ouverte dans votre navigateur.
                </p>
              </td></tr>
            </table>

            <table cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr>
                <td style="background:#0d1e38;border:1px solid #1e3a5f;border-left:3px solid {t.PRIMARY};
                  border-radius:0 10px 10px 0;padding:14px 16px;">
                  <p style="margin:0 0 5px;font-size:12px;font-weight:700;color:#93c5fd;">
                    &#8505;&#65039;&nbsp; Pourquoi ce code&#160;?
                  </p>
                  <p style="margin:0;font-size:12px;color:{t.MUTED};line-height:1.6;">
                    Ce code confirme que vous poss&#233;dez bien ce compte {provider_name}.
                    Une fois li&#233;, Argus surveillera les connexions inhabituelles
                    (nouvelle localisation, nouvel appareil, brute-force) et vous alertera.
                  </p>
                </td>
              </tr>
            </table>
    """

    return t.render_email(
        preheader=f"Code de vérification {provider_name} : {pin} — valable {expiry_minutes} minutes. Argus.",
        badge_label=provider_name,
        badge_letter=provider_letter,
        accent=provider_color,
        title=f"V&#233;rifiez votre compte {provider_name}",
        subtitle_html=(
            f"Une demande de liaison du compte "
            f"<strong style=\"color:{t.TEXT};\">&nbsp;{provider_email}&nbsp;</strong>"
            f"à votre espace Argus "
            f"(<span style=\"font-family:'Courier New',Courier,monospace;font-size:12px;color:{t.MUTED};\">{argus_user_email}</span>) "
            "a été initialisée."
        ),
        body_html=body,
        warning_html=(
            "Si vous n'avez pas initialisé cette liaison, ignorez cet email. "
            "Aucun compte ne sera lié et aucune action n'est requise."
        ),
    )
