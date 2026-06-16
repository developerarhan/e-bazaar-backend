from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.exceptions import AuthenticationFailed
import logging

logger = logging.getLogger('accounts')


# By default, DRF SimpleJWT reads tokens from the Authorization header. We need it to also check cookies. This is the most important piece of the whole implementation.
class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom authentication class that reads JWT from HttpOnly cookie
    instead of the Authorization header.
    
    Django REST Framework calls authenticate() on every request.
    We override it to check cookies first, then fall back to header.
    This means your API works for both browser clients (cookies)
    and mobile apps or third-party tools (Authorization header).
    """
    
    def authenticate(self, request):
        # First try to get token from cookie
        access_token = request.COOKIES.get(settings.AUTH_COOKIE)

        if access_token:
            # We found a cookie — validate it
            try:
                # This is SimpleJWT's built-in token validation
                validated_token = self.get_validated_token(access_token)
                user = self.get_user(validated_token)

                return (user, validated_token)
            
            except TokenError as e:
                # Token is expired or invalid
                # Don't raise here — fall through to header check
                # This allows the frontend to attempt a refresh
                logger.debug("Cookie token validation failed", extra={
                    "error": str(e),
                    "path": request.path,
                })
                raise AuthenticationFailed({
                    "detail": "Token expired",
                    "code": "token_expired",
                })
            
        # No cookie found — try Authorization header (fallback)
        # This calls the parent class's authenticate method
        # which reads from the Authorization: Bearer <token> header
        header_auth = super().authenticate(request)

        return header_auth  # returns None if no header either
    