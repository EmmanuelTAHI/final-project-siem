"""
Vues d'authentification : JWT login/refresh/logout + OAuth2 PKCE Microsoft/Google + Comptes liés.
"""
import logging
from urllib.parse import urlencode

from django.contrib.auth import authenticate
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from django.utils import timezone
from rest_framework_simplejwt.tokens import OutstandingToken, BlacklistedToken, RefreshToken

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.users.models import AuditTrail, User

from .models import LinkedAccount, LoginConfirmation, SecurityNotification
from .serializers import (
    LinkedAccountSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProviderLoginEventSerializer,
    SecurityNotificationSerializer,
)
from .services.link_oauth_service import link_oauth_service
from .services.login_email_service import (
    generate_login_otp,
    send_login_confirmation,
    verify_login_otp,
)
from .services.notification_service import notify, read_confirmation_token
from .services.oauth_service import oauth_service
from .services.password_reset_service import read_reset_token, send_password_reset_email
from .services.personal_security_service import check_own_login_impossible_travel
from apps.threat_intel.services.ip_enrichment import geo_lookup
from apps.logs.platform_events import record_platform_login

from utils.response import error_response, success_response

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class LoginView(APIView):
    """
    POST /api/auth/login/
    Authentifie l'utilisateur par email/mot de passe et retourne les tokens JWT.
    Rate limit : 10 tentatives par IP par minute.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Données invalides.",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=email, password=password)
        if not user:
            AuditTrail.log(
                action="login_failed",
                target_model="User",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT"),
                extra_data={"email": email},
            )
            return error_response(
                message="Email ou mot de passe incorrect.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return error_response(
                message="Ce compte est désactivé. Contactez l'administrateur.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        AuditTrail.log(
            action="login_credentials_ok",
            user=user,
            target_model="User",
            target_id=user.id,
            ip_address=ip,
            user_agent=ua,
        )

        # ── Anti-spam : ne pas renvoyer d'email si un OTP est déjà en attente ──
        cooldown_key = f"otp_cooldown:{user.id}"
        otp_key = f"login_otp:{user.id}"
        otp_already_live = cache.get(cooldown_key) and cache.get(otp_key)

        if not otp_already_live:
            otp_sent = send_login_confirmation(
                user,
                method="Mot de passe (compte Log+)",
                ip=ip,
                user_agent=ua,
                extra_intro=(
                    "Pour finaliser votre connexion, entrez le code ci-dessous "
                    "sur la plateforme Log+. Ce code est valide 10 minutes. "
                    "Sans ce code, la connexion ne peut pas aboutir."
                ),
            )
            if otp_sent is None:
                if getattr(settings, "DEBUG", False):
                    otp_sent = generate_login_otp(user.id)
                    logger.warning(
                        "[DEV] OTP pour %s : %s  (SMTP non configuré)",
                        user.email,
                        otp_sent,
                    )
                else:
                    return error_response(
                        message=(
                            "Le service d'envoi d'email est indisponible. "
                            "Contactez l'administrateur."
                        ),
                        http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
            # Cooldown 60s : fenêtre anti-spam inter-rechargements
            cache.set(cooldown_key, 1, 60)
            # Réinitialiser le compteur d'échecs OTP pour cette nouvelle session
            cache.delete(f"otp_attempts:{user.id}")

        # Token de pré-authentification (signé Django, max_age=600s côté verify)
        pre_auth_token = signing.dumps(
            {"user_id": str(user.id)},
            salt="logplus_pre_auth",
        )

        return success_response(
            data={
                "status": "otp_required",
                "pre_auth_token": pre_auth_token,
            },
            http_status=status.HTTP_200_OK,
            message="Code de vérification envoyé par email.",
        )


class TokenRefreshView(APIView):
    """
    POST /api/auth/token/refresh/
    Renouvelle l'access token via le refresh token.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token_str = request.data.get("refresh")
        if not refresh_token_str:
            return error_response(
                message="Le champ 'refresh' est requis.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = RefreshToken(refresh_token_str)
            return success_response(
                data={
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                },
                message="Token renouvelé avec succès.",
            )
        except TokenError as exc:
            return error_response(
                message=f"Token invalide ou expiré : {str(exc)}",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blackliste le refresh token pour invalider la session.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Le champ 'refresh' est requis.",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            refresh.blacklist()
            AuditTrail.log(
                action="logout",
                user=request.user,
                target_model="User",
                target_id=request.user.id,
                ip_address=get_client_ip(request),
            )
            return success_response(message="Déconnexion réussie.")
        except TokenError as exc:
            return error_response(
                message=f"Token invalide : {str(exc)}",
                http_status=status.HTTP_400_BAD_REQUEST,
            )


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/
    Envoie un email de réinitialisation si l'adresse correspond à un compte.
    Retourne toujours un message générique (pas d'énumération des comptes).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Données invalides.",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        generic_message = (
            "Si un compte existe avec cette adresse, un email de "
            "réinitialisation vient d'être envoyé."
        )

        try:
            user = User.objects.get(email=serializer.validated_data["email"], is_active=True)
        except User.DoesNotExist:
            return success_response(message=generic_message)

        send_password_reset_email(user)
        AuditTrail.log(
            action="password_reset_requested",
            user=user,
            target_model="User",
            target_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )
        return success_response(message=generic_message)


class PasswordResetConfirmView(APIView):
    """
    POST /api/auth/password-reset/confirm/
    Body: { "token": "<signed>", "password": "<nouveau mot de passe>" }
    Valide le token (30 min max), applique les règles de robustesse Django,
    puis change le mot de passe et révoque toutes les sessions actives.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Données invalides.",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        try:
            user_id = read_reset_token(token)
        except signing.SignatureExpired:
            return error_response(
                message="Ce lien de réinitialisation a expiré. Veuillez en redemander un.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            return error_response(
                message="Lien de réinitialisation invalide.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return error_response(
                message="Utilisateur introuvable ou inactif.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            return error_response(
                message="Mot de passe trop faible.",
                errors={"password": list(exc.messages)},
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=["password"])

        # Révoque toutes les sessions actives (l'utilisateur devra se reconnecter partout)
        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        AuditTrail.log(
            action="password_reset",
            user=user,
            target_model="User",
            target_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )
        return success_response(message="Mot de passe réinitialisé avec succès.")


class MicrosoftOAuthInitiateView(APIView):
    """
    GET /api/auth/oauth/microsoft/initiate/
    Génère le code_verifier PKCE et retourne l'URL d'autorisation Microsoft.
    Rate limit : 5 initiations par IP par 5 minutes.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = oauth_service.initiate_microsoft()
            return success_response(
                data=data,
                message="URL d'autorisation Microsoft générée. Redirigez l'utilisateur.",
            )
        except Exception as exc:
            logger.exception("Erreur lors de l'initiation OAuth Microsoft")
            return error_response(
                message=f"Erreur lors de l'initiation OAuth2 Microsoft : {str(exc)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MicrosoftOAuthCallbackView(APIView):
    """
    GET /api/auth/oauth/microsoft/callback/?code=...&state=...
    Traite le callback Microsoft, échange le code et stocke les tokens.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            return error_response(
                message=f"Erreur OAuth2 Microsoft : {request.query_params.get('error_description', error)}",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if not code or not state:
            return error_response(
                message="Les paramètres 'code' et 'state' sont requis.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token_data = oauth_service.callback_microsoft(code, state)
            return success_response(
                data={
                    "provider": "microsoft365",
                    "token_expires_at": token_data["token_expires_at"].isoformat(),
                    "message": "Authentification Microsoft réussie. Tokens stockés.",
                },
                message="Connexion Microsoft 365 établie avec succès.",
            )
        except ValueError as exc:
            return error_response(
                message=str(exc),
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Erreur callback OAuth Microsoft")
            return error_response(
                message=f"Erreur lors du traitement du callback Microsoft : {str(exc)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GoogleOAuthInitiateView(APIView):
    """
    GET /api/auth/oauth/google/initiate/
    Génère le code_verifier PKCE et retourne l'URL d'autorisation Google.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = oauth_service.initiate_google()
            return success_response(
                data=data,
                message="URL d'autorisation Google générée. Redirigez l'utilisateur.",
            )
        except Exception as exc:
            logger.exception("Erreur lors de l'initiation OAuth Google")
            return error_response(
                message=f"Erreur lors de l'initiation OAuth2 Google : {str(exc)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GoogleOAuthCallbackView(APIView):
    """
    GET /api/auth/oauth/google/callback/?code=...&state=...
    Traite le callback Google, échange le code et stocke les tokens.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            return error_response(
                message=f"Erreur OAuth2 Google : {error}",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if not code or not state:
            return error_response(
                message="Les paramètres 'code' et 'state' sont requis.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token_data = oauth_service.callback_google(code, state)
            return success_response(
                data={
                    "provider": "google_workspace",
                    "token_expires_at": token_data["token_expires_at"].isoformat(),
                    "message": "Authentification Google réussie. Tokens stockés.",
                },
                message="Connexion Google Workspace établie avec succès.",
            )
        except ValueError as exc:
            return error_response(
                message=str(exc),
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Erreur callback OAuth Google")
            return error_response(
                message=f"Erreur lors du traitement du callback Google : {str(exc)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ActiveSessionsView(APIView):
    """
    GET /api/auth/sessions/
    Retourne la liste des sessions actives de l'utilisateur connecté.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Récupérer tous les tokens non expirés et non blacklistés de l'utilisateur
        tokens = OutstandingToken.objects.filter(
            user=request.user,
            expires_at__gt=timezone.now()
        ).exclude(
            id__in=BlacklistedToken.objects.values_list('token_id', flat=True)
        ).order_by('-created_at')

        sessions = []
        current_token = request.auth  # Le token actuel de la requête

        for token in tokens:
            # Essayer de déterminer le navigateur et l'OS depuis l'audit trail
            # On prend le dernier login réussi pour ce token
            last_login = AuditTrail.objects.filter(
                user=request.user,
                action='login',
                timestamp__gte=token.created_at
            ).order_by('-timestamp').first()

            browser = "Navigateur inconnu"
            os = "OS inconnu"
            ip = token.jti  # Utilisons le JTI comme fallback pour l'IP, mais idéalement stocker l'IP dans OutstandingToken

            if last_login and last_login.user_agent:
                # Parser le user agent pour extraire navigateur et OS
                ua = last_login.user_agent.lower()
                if 'chrome' in ua and 'edg' not in ua:
                    browser = 'Chrome'
                elif 'firefox' in ua:
                    browser = 'Firefox'
                elif 'safari' in ua and 'chrome' not in ua:
                    browser = 'Safari'
                elif 'edg' in ua:
                    browser = 'Edge'
                elif 'opera' in ua:
                    browser = 'Opera'
                else:
                    browser = 'Navigateur inconnu'

                if 'windows' in ua:
                    os = 'Windows'
                elif 'mac' in ua or 'darwin' in ua:
                    os = 'macOS'
                elif 'linux' in ua:
                    os = 'Linux'
                elif 'android' in ua:
                    os = 'Android'
                elif 'ios' in ua or 'iphone' in ua or 'ipad' in ua:
                    os = 'iOS'
                else:
                    os = 'OS inconnu'

                ip = last_login.ip_address or ip

            sessions.append({
                'id': str(token.id),
                'device': f"{browser} / {os}",
                'ip': ip,
                'location': last_login.ip_address or '—' if last_login else '—',
                'current': str(token.id) == str(current_token.get('jti', '')) if current_token else False,
                'created_at': token.created_at.isoformat(),
                'expires_at': token.expires_at.isoformat(),
            })

        return success_response(
            data={'sessions': sessions},
            message="Sessions récupérées avec succès."
        )


# ═════════════════════════════════════════════════════════════════════════════
# COMPTES LIÉS (Google / Microsoft / GitHub)
# ═════════════════════════════════════════════════════════════════════════════


def _frontend_redirect(path: str, **params) -> HttpResponseRedirect:
    base = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    qs = "?" + urlencode(params) if params else ""
    return HttpResponseRedirect(f"{base}{path}{qs}")


class LinkedAccountInitiateView(APIView):
    """GET /api/auth/oauth/link/<provider>/initiate/ — renvoie l'URL d'autorisation."""

    permission_classes = [IsAuthenticated]

    def get(self, request, provider: str):
        try:
            data = link_oauth_service.initiate(provider, request.user.id)
        except ValueError as exc:
            return error_response(message=str(exc), http_status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("link initiate failed")
            return error_response(
                message="Erreur lors de l'initiation OAuth.",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return success_response(data=data, message="URL d'autorisation générée.")


class LinkedAccountCallbackView(APIView):
    """
    GET /api/auth/oauth/link/<provider>/callback/?code=&state=
    Callback IdP → crée/maj le LinkedAccount → redirige vers le frontend Settings.
    """

    permission_classes = [AllowAny]

    def get(self, request, provider: str):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        err = request.query_params.get("error")

        if err:
            return _frontend_redirect(
                "/settings",
                tab="linked_accounts",
                link_error=err,
                provider=provider,
            )
        if not code or not state:
            return _frontend_redirect(
                "/settings",
                tab="linked_accounts",
                link_error="missing_params",
                provider=provider,
            )

        try:
            verification = link_oauth_service.callback_with_pin(provider, code, state)
        except ValueError as exc:
            return _frontend_redirect(
                "/settings",
                tab="linked_accounts",
                link_error=str(exc)[:120],
                provider=provider,
            )
        except Exception:
            logger.exception("link callback failed")
            return _frontend_redirect(
                "/settings", tab="linked_accounts",
                link_error="internal_error", provider=provider,
            )

        return _frontend_redirect(
            "/settings",
            tab="linked_accounts",
            pin_required="1",
            verification_id=str(verification.id),
            provider=provider,
            email=verification.provider_email,
        )


class VerifyLinkPinView(APIView):
    """
    POST /api/auth/oauth/link/verify-pin/
    Vérifie le code PIN 4 chiffres et finalise la liaison du compte OAuth.
    Body: { "verification_id": "<uuid>", "pin": "1234" }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import AccountLinkVerification

        verification_id = request.data.get("verification_id", "").strip()
        pin = request.data.get("pin", "").strip()

        if not verification_id or not pin:
            return error_response(
                message="Les champs 'verification_id' et 'pin' sont requis.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            verification = AccountLinkVerification.objects.get(
                pk=verification_id,
                user=request.user,
            )
        except AccountLinkVerification.DoesNotExist:
            return error_response(
                message="Vérification introuvable.",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if verification.is_used:
            return error_response(
                message="Ce code a déjà été utilisé.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if not verification.is_valid:
            return error_response(
                message="Ce code a expiré. Veuillez relancer la liaison pour recevoir un nouveau code.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if verification.pin != pin:
            return error_response(
                message="Code PIN incorrect.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = link_oauth_service.finalize_link(verification)
        except Exception:
            logger.exception("finalize_link failed")
            return error_response(
                message="Erreur lors de la finalisation de la liaison.",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        AuditTrail.log(
            action="linked_account_added",
            user=request.user,
            target_model="LinkedAccount",
            target_id=account.id,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            extra_data={"provider": account.provider, "email": account.provider_email},
        )

        try:
            notify(
                request.user,
                kind="info", level="info",
                title=f"Compte {account.provider} lié avec succès",
                body=f"Le compte {account.provider_email} est maintenant surveillé par Log+.",
                linked_account=account,
                send_email=False,
                create_confirmation=False,
            )
        except Exception:
            logger.exception("notify on link failed")

        # Email "connexion réussie" + OTP côté provider
        try:
            send_login_confirmation(
                request.user,
                method=f"OAuth — {account.provider} ({account.provider_email})",
                ip=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                extra_intro=(
                    f"Votre compte {account.provider} ({account.provider_email}) "
                    f"vient d'être lié et activé sur Log+. Log+ va désormais "
                    f"surveiller en continu les évènements de connexion de ce compte."
                ),
            )
        except Exception:
            logger.exception("oauth login email failed for %s", request.user.email)

        return success_response(
            data={
                "provider": account.provider,
                "email": account.provider_email,
                "display_name": account.provider_display_name,
            },
            message=f"Compte {account.provider} lié avec succès.",
        )


class LinkedAccountListView(APIView):
    """GET /api/auth/linked-accounts/ — liste les comptes liés de l'utilisateur."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = LinkedAccount.objects.filter(user=request.user).order_by("-linked_at")
        return success_response(
            data={"accounts": LinkedAccountSerializer(qs, many=True).data},
            message="Comptes liés récupérés.",
        )


class LinkedAccountDetailView(APIView):
    """
    GET    /api/auth/linked-accounts/<uuid>/  — détail (avec 30 derniers events)
    DELETE /api/auth/linked-accounts/<uuid>/  — délier
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, account_id):
        account = get_object_or_404(LinkedAccount, pk=account_id, user=request.user)
        events = account.login_events.all().order_by("-occurred_at")[:30]
        return success_response(
            data={
                "account": LinkedAccountSerializer(account).data,
                "events": ProviderLoginEventSerializer(events, many=True).data,
            },
            message="Compte récupéré.",
        )

    def delete(self, request, account_id):
        account = get_object_or_404(LinkedAccount, pk=account_id, user=request.user)
        provider = account.provider
        provider_email = account.provider_email
        account.delete()
        AuditTrail.log(
            action="linked_account_removed",
            user=request.user, target_model="LinkedAccount", target_id=account_id,
            ip_address=get_client_ip(request),
            extra_data={"provider": provider, "email": provider_email},
        )
        return success_response(message="Compte délié.")


class LinkedAccountPollView(APIView):
    """POST /api/auth/linked-accounts/<uuid>/poll/ — déclenche un poll manuel."""

    permission_classes = [IsAuthenticated]

    def post(self, request, account_id):
        account = get_object_or_404(LinkedAccount, pk=account_id, user=request.user)
        from .services.personal_security_service import poll_account

        try:
            new_events = poll_account(account)
        except Exception as exc:
            logger.exception("manual poll failed")
            return error_response(message=f"Erreur poll : {exc}", http_status=500)
        return success_response(
            data={"new_events": new_events, "polled_at": timezone.now().isoformat()},
            message="Poll terminé.",
        )


# ═════════════════════════════════════════════════════════════════════════════
# CONFIRMATION DE CONNEXION
# ═════════════════════════════════════════════════════════════════════════════


class ConfirmLoginView(APIView):
    """
    POST /api/auth/confirm-login/<token>/ — body { action: "approve" | "reject" }

    Valide le token signé puis met à jour la LoginConfirmation.
    Si "reject" : pause le LinkedAccount + notification "compte verrouillé".

    AllowAny car le user peut être déconnecté quand il clique depuis l'email.
    """

    permission_classes = [AllowAny]

    def post(self, request, token: str):
        return self._handle(request, token, request.data.get("action", "").lower())

    def get(self, request, token: str):
        # Permet aussi GET pour les liens dans l'email — preview only
        try:
            confirmation_id = read_confirmation_token(token)
        except signing.SignatureExpired:
            return error_response(message="Lien expiré.", http_status=410)
        except signing.BadSignature:
            return error_response(message="Lien invalide.", http_status=400)

        confirmation = get_object_or_404(LoginConfirmation, pk=confirmation_id)
        return success_response(data={
            "confirmation": {
                "id": str(confirmation.id),
                "status": confirmation.status,
                "ip_address": confirmation.ip_address,
                "browser": confirmation.browser,
                "os": confirmation.os,
                "device_type": confirmation.device_type,
                "geo_city": confirmation.geo_city,
                "geo_country": confirmation.geo_country,
                "created_at": confirmation.created_at.isoformat(),
                "expires_at": confirmation.expires_at.isoformat(),
                "user_email": confirmation.user.email,
                "provider": confirmation.linked_account.provider if confirmation.linked_account else None,
                "provider_email": confirmation.linked_account.provider_email if confirmation.linked_account else None,
            }
        })

    def _handle(self, request, token, action):
        if action not in ("approve", "reject"):
            return error_response(
                message="Action invalide. Utilisez 'approve' ou 'reject'.",
                http_status=400,
            )
        try:
            confirmation_id = read_confirmation_token(token)
        except signing.SignatureExpired:
            return error_response(message="Lien expiré.", http_status=410)
        except signing.BadSignature:
            return error_response(message="Lien invalide.", http_status=400)

        confirmation = get_object_or_404(LoginConfirmation, pk=confirmation_id)
        if confirmation.status != "pending":
            return error_response(
                message=f"Confirmation déjà traitée ({confirmation.status}).",
                http_status=409,
            )
        if confirmation.expires_at <= timezone.now():
            confirmation.status = "expired"
            confirmation.save(update_fields=["status"])
            return error_response(message="Confirmation expirée.", http_status=410)

        confirmation.status = "approved" if action == "approve" else "rejected"
        confirmation.responded_at = timezone.now()
        confirmation.responded_ip = get_client_ip(request)
        confirmation.save(update_fields=["status", "responded_at", "responded_ip"])

        if action == "reject" and confirmation.linked_account:
            account = confirmation.linked_account
            account.status = "paused"
            account.save(update_fields=["status", "updated_at"])
            try:
                notify(
                    confirmation.user,
                    kind="account_locked", level="critical",
                    title=f"Compte {account.provider} mis en pause",
                    body=(
                        f"Vous avez signalé une connexion non reconnue. Le compte "
                        f"{account.provider} ({account.provider_email}) a été mis en pause. "
                        f"Changez votre mot de passe côté {account.provider} et révoquez les sessions actives."
                    ),
                    linked_account=account, send_email=True, create_confirmation=False,
                )
            except Exception:
                logger.exception("notify after rejection failed")

        AuditTrail.log(
            action=f"login_confirmation_{confirmation.status}",
            user=confirmation.user,
            target_model="LoginConfirmation",
            target_id=confirmation.id,
            ip_address=get_client_ip(request),
        )
        return success_response(
            data={"status": confirmation.status},
            message="Réponse enregistrée.",
        )


# ═════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS DE SÉCURITÉ
# ═════════════════════════════════════════════════════════════════════════════


class VerifyLoginOTPView(APIView):
    """
    POST /api/auth/verify-otp/
    Étape 2 du login : vérifie l'OTP reçu par email et émet les tokens JWT.
    Body: { "pre_auth_token": "<signed>", "otp": "123456" }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        pre_auth_token = str(request.data.get("pre_auth_token", "")).strip()
        otp = str(request.data.get("otp", "")).strip()

        if not pre_auth_token or not otp:
            return error_response(
                message="Les champs 'pre_auth_token' et 'otp' sont requis.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # Décoder et valider le token de pré-authentification (max 10 min)
        try:
            payload = signing.loads(
                pre_auth_token,
                salt="logplus_pre_auth",
                max_age=600,
            )
            user_id = payload["user_id"]
        except signing.SignatureExpired:
            return error_response(
                message="Session expirée. Veuillez relancer la connexion.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            return error_response(
                message="Token de pré-authentification invalide.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # Récupérer l'utilisateur
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return error_response(
                message="Utilisateur introuvable ou inactif.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # ── Limite de tentatives : max 5 avant invalidation de la session ─────
        attempts_key = f"otp_attempts:{user.id}"
        attempts = cache.get(attempts_key, 0)
        MAX_ATTEMPTS = 5

        if attempts >= MAX_ATTEMPTS:
            cache.delete(f"login_otp:{user.id}")
            cache.delete(attempts_key)
            return error_response(
                message="Trop de tentatives incorrectes. Veuillez relancer la connexion.",
                http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Vérifier l'OTP (le cache le détruit après vérification → usage unique)
        if not verify_login_otp(user.id, otp):
            new_attempts = attempts + 1
            remaining = MAX_ATTEMPTS - new_attempts
            if remaining <= 0:
                cache.delete(f"login_otp:{user.id}")
                cache.delete(attempts_key)
                return error_response(
                    message="Code invalide. Trop de tentatives. Veuillez relancer la connexion.",
                    http_status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            cache.set(attempts_key, new_attempts, 600)
            return error_response(
                message=f"Code OTP invalide ou expiré. {remaining} tentative(s) restante(s).",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # OTP correct → nettoyer les clés de session et émettre les tokens JWT
        cache.delete(attempts_key)
        cache.delete(f"otp_cooldown:{user.id}")
        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["full_name"] = user.full_name

        login_ip = get_client_ip(request)
        geo = geo_lookup(login_ip)
        geo_country = (geo.get("countryCode") or "")[:2]
        geo_city = geo.get("city") or ""

        try:
            check_own_login_impossible_travel(user, login_ip, geo_country, geo_city)
        except Exception:
            logger.exception("check_own_login_impossible_travel failed")

        AuditTrail.log(
            action="login",
            user=user,
            target_model="User",
            target_id=user.id,
            ip_address=login_ip,
            user_agent=request.META.get("HTTP_USER_AGENT"),
            geo_country=geo_country,
            geo_city=geo_city,
        )

        try:
            record_platform_login(
                user_email=user.email,
                success=True,
                ip_address=login_ip,
                geo_country=geo_country,
                geo_city=geo_city,
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except Exception:
            logger.exception("record_platform_login failed")

        return success_response(
            data={
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "token_type": "Bearer",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                },
            },
            message="Connexion réussie.",
        )


class ResendOTPView(APIView):
    """
    POST /api/auth/resend-otp/
    Régénère et renvoie un nouvel OTP pour une session de pré-authentification.
    Body: { "pre_auth_token": "<signed>" }
    Limité à 3 renvois par token (compteur Redis).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        pre_auth_token = str(request.data.get("pre_auth_token", "")).strip()
        if not pre_auth_token:
            return error_response(
                message="Le champ 'pre_auth_token' est requis.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = signing.loads(
                pre_auth_token,
                salt="logplus_pre_auth",
                max_age=600,
            )
            user_id = payload["user_id"]
        except signing.SignatureExpired:
            return error_response(
                message="Session expirée. Veuillez relancer la connexion.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            return error_response(
                message="Token invalide.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return error_response(
                message="Utilisateur introuvable.",
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # Limite anti-abus : max 3 renvois par session
        resend_key = f"otp_resend_count:{user_id}"
        resend_count = cache.get(resend_key, 0)
        if resend_count >= 3:
            return error_response(
                message="Nombre maximum de renvois atteint. Relancez la connexion.",
                http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        cache.set(resend_key, resend_count + 1, 600)

        ip = get_client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")
        otp_sent = send_login_confirmation(
            user,
            method="Mot de passe (renvoi OTP)",
            ip=ip,
            user_agent=ua,
            extra_intro=(
                "Voici votre nouveau code de connexion Log+. "
                "Entrez-le sur la plateforme pour finaliser votre connexion. "
                "Ce code est valide 10 minutes."
            ),
        )

        if otp_sent is None:
            if getattr(settings, "DEBUG", False):
                otp_sent = generate_login_otp(user.id)
                logger.warning("[DEV] OTP renvoyé pour %s : %s", user.email, otp_sent)
            else:
                return error_response(
                    message="Service d'email indisponible.",
                    http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        return success_response(message="Nouveau code envoyé par email.")


class NotificationListView(APIView):
    """GET /api/auth/notifications/?unread_only=1 — liste des notifications."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = request.query_params.get("unread_only") in ("1", "true", "yes")
        qs = SecurityNotification.objects.filter(user=request.user)
        if unread_only:
            qs = qs.filter(is_read=False)
        qs = qs.order_by("-created_at")[:100]
        return success_response(data={
            "notifications": SecurityNotificationSerializer(qs, many=True).data,
            "unread_count": SecurityNotification.objects.filter(user=request.user, is_read=False).count(),
        })


class NotificationMarkReadView(APIView):
    """POST /api/auth/notifications/<uuid>/read/   ou   /api/auth/notifications/read-all/."""

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id=None):
        if notification_id:
            notif = get_object_or_404(
                SecurityNotification, pk=notification_id, user=request.user
            )
            if not notif.is_read:
                notif.is_read = True
                notif.read_at = timezone.now()
                notif.save(update_fields=["is_read", "read_at"])
            return success_response(message="Notification marquée comme lue.")
        # read all
        SecurityNotification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return success_response(message="Toutes les notifications marquées comme lues.")
