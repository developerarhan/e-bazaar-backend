from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger('accounts')


def send_verification_email(user, token):
    """
    Sends the email verification link to the user.
    """
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')

    verification_url = f"{frontend_url}/verify-email?token={token.token}"

    subject = "Verify your E-Bazaar account"

    # Plain text version — always include for email clients
    # that don't render HTML
    plain_message = f"""
Hi {user.name},

Welcome to E-Bazaar! Please verify your email address by clicking the link below:

{verification_url}

This link expires in 24 hours.

If you didn't create an account, ignore this email.

— The E-Bazaar Team
    """.strip()

    html_message = render_to_string(
        'emails/verify_email.html',
        {
            'user': user,
            'verification_url': verification_url,
        }
    )

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,  # raise exception if sending fails
    )

    logger.info("Verification email sent", extra={
        "user_id": user.id,
        "email": user.email,
    })


def send_welcome_email(user):
    """
    Sent after user successfully verifies their email.
    This replaces your old send_welcome_email_task.
    """
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')

    subject = "Welcome to E-Bazaar!"

    plain_message = f"""
Hi {user.name},

Your email has been verified. Welcome to E-Bazaar!

Start shopping: {frontend_url}/products

— The E-Bazaar Team
    """.strip()

    html_message = render_to_string(
        'emails/welcome.html',
        {
            'user': user,
            'frontend_url': frontend_url,
        }
    )

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,  # welcome email failing is not critical
    )