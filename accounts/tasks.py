from celery import shared_task
from django.core.mail import get_connection
import logging
import time
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import User, EmailVerificationToken
from .emails import send_verification_email

logger = logging.getLogger('accounts')


@shared_task(
    bind=True,
    max_retries=5,  # email delivery can be flaky
    default_retry_delay=30, # retry after 30 seconds
    name='accounts.send_verification_email'
)
def send_verification_email_task(self, user_id):
    """
    Sends email verification link to newly registered user.
    This replaces send_welcome_email_task entirely.

    Why Celery for this?
    Sending email can take 1-3 seconds.
    Without Celery, your registration endpoint takes 1-3 seconds.
    With Celery, registration returns in milliseconds.
    Email is sent in the background.
    """
    try:
        from accounts.models import User, EmailVerificationToken
        from accounts.emails import send_verification_email

        user = User.objects.get(id=user_id)

        # Get existing token or create new one
        # delete_or_create pattern: always fresh token on retry
        EmailVerificationToken.objects.filter(user=user).delete()
        token = EmailVerificationToken.objects.create(user=user)

        send_verification_email(user, token)

        logger.info("Verification email sent", extra={
            "user_id": user_id,
            "email": user.email,
        })

        return f"Verification email sent to {user.email}"

    except User.DoesNotExist:
        # Don't retry — user doesn't exist
        logger.error("User not found for verification email", extra={
            "user_id": user_id,
        })
        return f"User {user_id} not found"

    except Exception as exc:
        logger.error("Failed to send verification email", extra={
            "user_id": user_id,
            "error": str(exc),
            "attempt": self.request.retries + 1,
        })
        raise self.retry(exc=exc)


@shared_task(
    name='accounts.cleanup_expired_tokens',
)
def cleanup_expired_tokens():
    """
    Runs daily via Celery Beat.
    Deletes expired, unused verification tokens.
    Keeps your database clean.
    """
    from django.utils import timezone
    from datetime import timedelta

    expiry_time = timezone.now() - timedelta(hours=24)

    deleted_count, _ = EmailVerificationToken.objects.filter(
        created_at__lt=expiry_time,
        is_used=False,
    ).delete()

    logger.info("Cleaned up expired verification tokens", extra={
        "deleted_count": deleted_count,
    })

    return deleted_count

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name='accounts.send_password_reset_email'
)
def send_password_reset_email_task(self, user_id, reset_url):
    """
    Sends password reset email in background.
    """
    try:
        from accounts.models import User

        user = User.objects.get(id=user_id)

        html_message = render_to_string(
            'emails/password_reset.html',
            {
                'user': user,
                'reset_url': reset_url,
            }
        )

        plain_message = (
            f"Hi {user.name},\n\n"
            f"Reset your e-Bazaar password:\n{reset_url}\n\n"
            f"Expires in 1 hour.\n\n"
            f"— e-Bazaar"
        )

        send_mail(
            subject="Reset your e-Bazaar password",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info("Password reset email sent", extra={'user_id': user_id})
        return f"Reset email sent to {user.email}"

    except User.DoesNotExist:
        return f"User {user_id} not found"

    except Exception as exc:
        logger.error("Failed to send password reset email", extra={
            'user_id': user_id,
            'error': str(exc),
        })
        raise self.retry(exc=exc)
