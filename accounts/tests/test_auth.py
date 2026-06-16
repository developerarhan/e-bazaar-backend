import pytest
from django.urls import reverse
from django.test import TestCase
from django.core import mail
from accounts.models import User, EmailVerificationToken


@pytest.mark.django_db
class TestRegisterView:

    def test_register_success(self, api_client):
        """New user can register with valid data."""
        response = api_client.post('/api/accounts/register/', {
            'name': 'John Doe',
            'email': 'john@test.com',
            'password': 'StrongPass1!',
            'confirm_password': 'StrongPass1!',
        })

        assert response.status_code == 201
        assert response.data['email'] == 'john@test.com'
        assert User.objects.filter(email='john@test.com').exists()

        # User starts as inactive until email verified
        user = User.objects.get(email='john@test.com')
        assert user.is_active is False

    def test_register_sends_verification_email(self, api_client, django_capture_on_commit_callbacks):
        """Verification email is sent after registration."""
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = api_client.post('/api/accounts/register/', {
            'name': 'John Doe',
            'email': 'john@test.com',
            'password': 'StrongPass1!',
            'confirm_password': 'StrongPass1!',
        })

        # locmem backend stores emails in mail.outbox
        assert len(mail.outbox) == 1
        assert 'john@test.com' in mail.outbox[0].to
        assert 'verify' in mail.outbox[0].subject.lower()

    def test_register_duplicate_email(self, api_client, verified_user):
        """Cannot register with an already-used email."""  
        response = api_client.post('/api/accounts/register/', {
            'name': 'Another John',
            'email': verified_user.email,   # already exists
            'password': 'StrongPass1!',
            'confirm_password': 'StrongPass1!',
        })

        assert response.status_code == 400
        assert 'email' in response.data

    def test_register_weak_password(self, api_client):
        """Weak password is rejected by validators."""
        response = api_client.post('/api/accounts/register/', {
            'name': 'John Doe',
            'email': 'john@test.com',
            'password': 'weakpassword',   # no uppercase, number, special
            'confirm_password': 'weakpassword',
        })

        assert response.status_code == 400
        assert 'password' in response.data

    def test_register_password_mismatch(self, api_client):
        """Mismatched passwords are rejected."""
        response = api_client.post('/api/accounts/register/', {
            'name': 'John Doe',
            'email': 'john@test.com',
            'password': 'StrongPass1!',
            'confirm_password': 'DifferentPass1!',
        })

        assert response.status_code == 400


@pytest.mark.django_db
class TestLoginView:
    
    def test_login_success(self, api_client, verified_user):
        """Verified user can login."""
        response = api_client.post('/api/accounts/login/', {
            'email': verified_user.email,
            'password': 'TestPass1!',
        })

        assert response.status_code == 200
        assert response.data['user']['email'] == verified_user.email
        # Tokens should be in cookies, not response body
        assert 'access_token' in response.cookies
        assert 'refresh_token' in response.cookies
        # Cookies must be HttpOnly
        assert response.cookies['access_token']['httponly']

    def test_login_wrong_password(self, api_client, verified_user):
        """Wrong password is rejected."""
        response = api_client.post('/api/accounts/login/', {
           'email': verified_user.email,
            'password': 'WrongPassword1!', 
        })
        assert response.status_code == 400

    def test_login_unverified_user(self, api_client, unverified_user):
        """Unverified user cannot login."""
        response = api_client.post('/api/accounts/login/', {
            'email': unverified_user.email,
            'password': 'TestPass1!',
        })
        # Should fail — account not active
        assert response.status_code == 400

    def test_login_nonexistent_email(self, api_client):
        """Non-existent email is rejected."""
        response = api_client.post('/api/accounts/login/', {
            'email': 'nobody@test.com',
            'password': 'TestPass1!',
        })
        assert response.status_code == 400


@pytest.mark.django_db
class TestEmailVerification:

    def test_verify_email_success(self, api_client, unverified_user):
        """Valid token activates the user."""
        token = EmailVerificationToken.objects.create(
            user=unverified_user
        )
    
        response = api_client.post('/api/accounts/verify-email/', {
            'token': str(token.token),
        })

        assert response.status_code == 200
        unverified_user.refresh_from_db()
        assert unverified_user.is_active is True

        # Token marked as used
        token.refresh_from_db()
        assert token.is_used is True


    def test_verify_email_invalid_token(self, api_client):
        """Invalid token is rejected."""
        response = api_client.post('/api/accounts/verify-email/', {
            'token': 'invalid-token-value',
        })
        assert response.status_code == 400

    def test_verify_email_already_used(self, api_client, unverified_user):
        """Already-used token cannot be reused."""
        token = EmailVerificationToken.objects.create(
            user=unverified_user,
            is_used=True,   # already used
        )

        response = api_client.post('/api/accounts/verify-email/', {
            'token': str(token.token),
        })

        assert response.status_code == 400


@pytest.mark.django_db
class TestPasswordReset:

    def test_request_reset_success(self, api_client, verified_user, django_capture_on_commit_callbacks):
        """Reset email sent for valid email."""
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post('/api/accounts/password-reset/', {
            'email': verified_user.email,
        })

        assert response.status_code == 200
        assert len(mail.outbox) == 1
        assert 'reset' in mail.outbox[0].subject.lower()

    def test_request_reset_unknown_email(self, api_client):
        response = api_client.post('/api/accounts/password-reset/', {
            'email': 'nobody@test.com',
        })

        # Must return 200 — don't reveal email existence
        assert response.status_code == 200
        # No email sent
        assert len(mail.outbox) == 0

    def test_request_reset_oauth_user(self, api_client, oauth_user):
        """OAuth users get a specific error message."""
        response = api_client.post('/api/accounts/password-reset/', {
            'email': oauth_user.email,
        })

        assert response.status_code == 400
        assert 'google' in response.data['error'].lower()
        assert response.data['auth_provider'] == 'google'

    def test_confirm_reset_success(self, api_client, verified_user):
        """Valid token + strong password resets successfully."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        uid = urlsafe_base64_encode(force_bytes(verified_user.pk))
        token = default_token_generator.make_token(verified_user)

        response = api_client.post('/api/accounts/password-reset-confirm/', {
            'uidb64': uid,
            'token': token,
            'new_password': 'NewStrongPass1!',
        })

        assert response.status_code == 200

        # Verify password actually changed
        verified_user.refresh_from_db()
        assert verified_user.check_password('NewStrongPass1!') is True
        assert verified_user.check_password('TestPass1!') is False

    def test_confirm_reset_invalid_token(self, api_client, verified_user):
        """Invalid token is rejected."""
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        uid = urlsafe_base64_encode(force_bytes(verified_user.pk))

        response = api_client.post('/api/accounts/password-reset-confirm/', {
            'uidb64': uid,
            'token': 'invalid-token',
            'new_password': 'NewStrongPass1!',
        })

        assert response.status_code == 400

    def test_confirm_reset_weak_password(self, api_client, verified_user):
        """Weak new password is rejected."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        uid = urlsafe_base64_encode(force_bytes(verified_user.pk))
        token = default_token_generator.make_token(verified_user)

        response = api_client.post('/api/accounts/password-reset-confirm/', {
            'uidb64': uid,
            'token': token,
            'new_password': 'weak',
        })

        assert response.status_code == 400
