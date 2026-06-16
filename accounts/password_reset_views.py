import logging
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import User

logger = logging.getLogger('accounts')


class PasswordResetRequestView(APIView):
    """
    POST /api/accounts/password-reset/
    Body: { "email": "user@example.com" }

    Sends a password reset link to the user's email.
    """

    def post(self, request):
        email = request.data.get('email', '').strip().lower()

        if not email:
            return Response(
                {'error': 'Email is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Always return same response regardless of whether
        # email exists — prevents user enumeration attacks
        # (attacker can't tell which emails are registered)
        success_response = Response({
            'message': (
                'If an account with that email exists, '
                'a reset link has been sent.'
            )
        })

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal that email doesn't exist
            logger.warning("Password reset for unknown email", extra={
                'email': email,
                'ip': request.META.get('REMOTE_ADDR'),
            })
            return success_response
        
        # ── OAuth users cannot reset password ────────────────────
        # They don't have a password — they use Google to login
        if user.is_oauth_user:
            logger.info("OAuth user tried to reset password", extra={
                'user_id': user.id,
                'auth_provider': user.auth_provider,
            })
            #   tell them to use Google
            return Response(
                {
                    'error': (
                        f'This account uses {user.auth_provider.title()} login. '
                        f'Please sign in with {user.auth_provider.title()} instead.'
                    ),
                    'auth_provider': user.auth_provider,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ── Generate secure reset token ───────────────────────────
        # uidb64: base64-encoded user primary key
        # token:  Django's built-in token (expires after 1 hour by default,
        #         and invalidates the moment password changes)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

         # ── Build frontend reset URL
        frontend_url = getattr(
            settings, 'FRONTEND_URL', 'http://localhost:5173',
        )
        reset_url = f"{frontend_url}/reset-password/{uid}/{token}/"

        # ── Send email
        try:
            from accounts.tasks import send_password_reset_email_task

            transaction.on_commit(
                lambda: send_password_reset_email_task.delay(user.id, reset_url)
            )

            logger.info(
                "Password reset email queued",
                extra={'user_id': user.id}
            )
        
        except Exception as e:
            logger.error("Failed to send password reset email", extra={
                'user_id': user.id,
                'error': str(e),
            }, exc_info=True)

        return success_response


class PasswordResetConfirmView(APIView):
    """
    POST /api/accounts/password-reset-confirm/
    Body: {
        "uidb64": "...",
        "token": "...",
        "new_password": "..."
    }

    Validates the token and sets the new password.
    """

    def post(self, request):
        uidb64 = request.data.get('uidb64', '').strip()
        token = request.data.get('token', '').strip()
        new_password = request.data.get('new_password', '')

        # Valdiate required fields
        if not uidb64 or not token:
            return Response(
                {'error': 'Invalid reset link.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not new_password:
            return Response(
                {'error': 'New password is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Decode user form uidb64
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            logger.warning("Password reset with invalid uid", extra={
                'uidb64': uidb64,
                'ip': request.META.get('REMOTE_ADDR'),
            })
            return Response(
                {'error': 'This reset link is invalid.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate token
        # default_token_generator.check_token() returns False if:
        #   - Token is tampered with
        #   - Token is expired (default: 1 hour, set by PASSWORD_RESET_TIMEOUT)
        #   - Password was already changed (token auto-invalidates)
        if not default_token_generator.check_token(user, token):
            logger.warning("Password reset with invalid/expired token", extra={
                 'user_id': user.id,
                'ip': request.META.get('REMOTE_ADDR'),
            })
            return Response(
                {
                    'error': 'This reset link is invalid or has expired.',
                    'code': 'token_invalid',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate new password strength
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response(
                {'error': list(e.messages)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # set new password
        # set_password() hashes the password
        # After save(), the token auto-invalidates because
        # token is based on password hash — which just changed
        user.set_password(new_password)
        user.save()

        # Blacklist all existing JWT refresh tokens
        # User changed password - all existing sessions should end
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                OutstandingToken,
                BlacklistedToken,
            )
            # Get all outstanding tokens for this user
            tokens = OutstandingToken.objects.filter(user=user)
            for t in tokens:
                BlacklistedToken.objects.get_or_create(token=t)

        except Exception as e:
            # Non-critical — log but don't fail
            logger.warning("Could not blacklist tokens after password reset", extra={
                'user_id': user.id,
                'error': str(e),
            })

        logger.info("Password reset successful", extra={
            'user_id': user.id,
        })

        return Response({
            'message': (
                'Password reset successful. '
                'You can now log in with your new password.'
            )
        })
    

class PasswordResetValidateView(APIView):
    """
    GET /api/accounts/password-reset-validate/<uidb64>/<token>/

    Frontend calls this when reset page loads
    to check if link is still valid BEFORE
    showing the new password form.

    Prevents user from filling out form only to
    find out the link expired on submit.
    """

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {
                    'valid': False,
                    'error': 'This reset link is invalid.',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not default_token_generator.check_token(user, token):
            return Response(
                {
                    'valid': False,
                    'error': 'This reset link has expired.',
                    'code': 'token_expired',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valid — tell frontend to show the form
        return Response({
            'valid': True,
            'email': user.email,    # show user which account they're resetting
        })