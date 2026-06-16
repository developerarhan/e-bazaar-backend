from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # OAuth users have no password
            user.set_unusable_password()
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)  # superuser skips verification
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    profile_image = models.URLField(blank=True, null=True)  # ← URLField now  # stores Google avatar URL

    # OAuth fields
    auth_provider = models.CharField(
        max_length=20,
        default='email',       # 'email', 'google', 'github'
    )
    google_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    @property
    def is_oauth_user(self):
        return self.auth_provider != 'email'

    def __str__(self):
        return self.email
    
class EmailVerificationToken(models.Model):

    """
    Stores the one-time token sent to a user's email.
    One token per user at a time.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='email_verification_token'
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        """
        Token is valid if:
        1. It has not been used
        2. It was created less than 24 hours ago
        """
        from django.utils import timezone
        from datetime import timedelta

        if self.is_used:
            return False
        
        expiry_time = self.created_at + timedelta(hours=24)
        return timezone.now() < expiry_time
    
    def __str__(self):
        return f"Verification token for {self.user.email}"
    