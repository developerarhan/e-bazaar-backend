from django.urls import path
from django.conf import settings

from .views import RegisterView, LoginView, LogoutView, TokenRefreshView, ProfileView, VerifyEmailView,ResendVerificationView
from .oauth_views import GoogleOAuthView, GoogleOAuthCallbackView, GoogleOAuthDebugView
from .password_reset_views import (
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordResetValidateView,
)

urlpatterns = [
    # Auth
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", ProfileView.as_view(), name="profile"),
    
    # Email verification
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend_verification"),

    # OAuth2
    path("oauth/google/", GoogleOAuthView.as_view(), name="google_oauth"),
    path("oauth/google/callback/", GoogleOAuthCallbackView.as_view(), name="google_callback"),

    # Password reset
    path("password-reset/", PasswordResetRequestView.as_view()),
    path("password-reset-confirm/", PasswordResetConfirmView.as_view()),
    path("password-reset-validate/<str:uidb64>/<str:token>/", PasswordResetValidateView.as_view()),
]

# Only in development
if settings.DEBUG:
    urlpatterns += [
        path("oauth/debug/", GoogleOAuthDebugView.as_view()),
    ]