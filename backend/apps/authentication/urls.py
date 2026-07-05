from django.urls import path

from .views import (
    ActiveSessionsView,
    ConfirmLoginView,
    GoogleOAuthCallbackView,
    GoogleOAuthInitiateView,
    LinkedAccountCallbackView,
    LinkedAccountDetailView,
    LinkedAccountInitiateView,
    LinkedAccountListView,
    LinkedAccountPollView,
    LoginView,
    LogoutView,
    MicrosoftOAuthCallbackView,
    MicrosoftOAuthInitiateView,
    NotificationListView,
    NotificationMarkReadView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendOTPView,
    TokenRefreshView,
    VerifyLinkPinView,
    VerifyLoginOTPView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("sessions/", ActiveSessionsView.as_view(), name="auth-sessions"),

    # OAuth ingestion connecteurs (existant)
    path("oauth/microsoft/initiate/", MicrosoftOAuthInitiateView.as_view(), name="oauth-microsoft-initiate"),
    path("oauth/microsoft/callback/", MicrosoftOAuthCallbackView.as_view(), name="oauth-microsoft-callback"),
    path("oauth/google/initiate/", GoogleOAuthInitiateView.as_view(), name="oauth-google-initiate"),
    path("oauth/google/callback/", GoogleOAuthCallbackView.as_view(), name="oauth-google-callback"),

    # OAuth liaison de comptes personnels
    path("oauth/link/<str:provider>/initiate/", LinkedAccountInitiateView.as_view(), name="link-initiate"),
    path("oauth/link/<str:provider>/callback/", LinkedAccountCallbackView.as_view(), name="link-callback"),
    path("oauth/link/verify-pin/", VerifyLinkPinView.as_view(), name="link-verify-pin"),

    path("linked-accounts/", LinkedAccountListView.as_view(), name="linked-accounts-list"),
    path("linked-accounts/<uuid:account_id>/", LinkedAccountDetailView.as_view(), name="linked-accounts-detail"),
    path("linked-accounts/<uuid:account_id>/poll/", LinkedAccountPollView.as_view(), name="linked-accounts-poll"),

    # Notifications de sécurité
    path("notifications/", NotificationListView.as_view(), name="notifications-list"),
    path("notifications/read-all/", NotificationMarkReadView.as_view(), name="notifications-read-all"),
    path("notifications/<uuid:notification_id>/read/", NotificationMarkReadView.as_view(), name="notifications-read"),

    # Vérification OTP — étape 2 obligatoire du login
    path("verify-otp/", VerifyLoginOTPView.as_view(), name="auth-verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="auth-resend-otp"),

    # Confirmation de connexion (lien email)
    path("confirm-login/<str:token>/", ConfirmLoginView.as_view(), name="confirm-login"),
]
