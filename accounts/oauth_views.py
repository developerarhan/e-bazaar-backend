import logging
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .cookies import set_auth_cookies

logger = logging.getLogger('accounts')


class GoogleOAuthView(APIView):
    """
    Step 1: Generate Google OAuth URL
    Frontend calls this to get the URL to redirect user to Google.

    GET /api/accounts/oauth/google/
    Returns: { auth_url: "https://accounts.google.com/o/oauth2/..." }
    """

    def get(self, request):
        import urllib.parse

        # Build Google's authorization URL
        params = {
            'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent select_account',
        }

        auth_url = (
            'https://accounts.google.com/o/oauth2/v2/auth?'
            + urllib.parse.urlencode(params)
        )

        return Response({'auth_url': auth_url})
    


class GoogleOAuthCallbackView(APIView):
    """
    Step 2: Handle Google's callback
    Google redirects to frontend with ?code=xxx
    Frontend sends that code to THIS endpoint.

    POST /api/accounts/oauth/google/callback/
    Body: { code: "xxx" }
    Returns: user data + sets HttpOnly cookies
    """

    def post(self, request):
        code = request.data.get('code')

        if not code:
            return Response(
                {'error': 'Authentication code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Step 1: Exchange code for tokens 
            google_tokens = self._exchange_code_for_tokens(code)

            if 'error' in google_tokens:
                logger.warning(
                    "Google token exchange failed", extra={
                    'error': google_tokens.get('error'),
                })
                return Response(
                    {'error': 'Failed to authenticate with Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Step 2: Get user info from Google 
            user_info = self._get_google_user_info(
                google_tokens['access_token']
            )

            logger.info("Google returned user", extra={
                'email': user_info.get('email'),
                'google_id': user_info.get('sub'),
            })

            if 'error' in user_info:
                return Response(
                    {'error': 'Failed to get user info from Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Step 3: Create or get user
            user, created = self._get_or_create_user(user_info)

            # Step 4: Issue your JWT tokens
            refresh = RefreshToken.for_user(user)

            logger.info(
                "User logged in via Google OAuth",
                extra={
                    'user_id': user.id,
                    'email': user.email,
                    'new_user': created,
                }
            )

            response = Response({
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'profile_image': user.profile_image,
                    'auth_provider': user.auth_provider,
                },
                'is_new_user': created,
            })

            # Set HttpOnly cookies — same as regular login
            set_auth_cookies(
                response,
                access_token=str(refresh.access_token),
                refresh_token=str(refresh),
            )

            return response

        except Exception as e:
            logger.error("Google OAuth error", extra={
                'error': str(e),
            }, exc_info=True)
            return Response(
                {'error': 'Authentication failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _exchange_code_for_tokens(self, code):
        """
        Exchange the authorization code for Google tokens.
        This is server-to-server communication — secure.
        """
        response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                'client_secret': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                'redirect_uri': settings.GOOGLE_REDIRECT_URI,
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        return response.json()
    
    def _get_google_user_info(self, access_token):
        """
        Use Google's access token to get user profile info.
        """
        response = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"User info fetch failed: {response.text}")
        
        return response.json()
    
    def _get_or_create_user(self, user_info):
        """
        Find existing user or create new one from Google data.

        Cases:
        1. New user → create account, mark as active (Google verified email)
        2. Existing user with same email (registered normally) → link accounts
        3. Existing Google user → just log them in
        """
        email = user_info.get('email')
        google_id = user_info.get('sub')
        name = user_info.get('name', '')
        picture = user_info.get('picture', '')

        if not email:
            raise ValueError("Google did not return an email address")

        if not google_id:
            raise ValueError("Google did not return a user ID")

        # Case 3: existing Google user
        try:
            user = User.objects.get(google_id=google_id)
            # Update profile picture in case it changed
            if picture and user.profile_image != picture:
                # Update profile picture in case it changed
                user.profile_image = picture
                user.save(update_fields=['profile_image'])
            return user, False
        
        except User.DoesNotExist:
            pass

        # Case 2: existing email user — link Google to their account
        try:
            user = User.objects.get(email=email)
            user.google_id = google_id
            user.auth_provider = 'google'
            if picture:
                user.profile_image = picture
            # Google verified their email — activate if not already
            user.is_active = True
            user.save(update_fields=[
                'google_id', 'auth_provider',
                'profile_image', 'is_active'
            ])
            return user, False

        except User.DoesNotExist:
            pass

        # Case 1: new user
        user = User.objects.create_user(
            email=email,
            name=name,
            profile_image=picture,
            auth_provider='google',
            google_id=google_id,
            is_active=True, # Google already verified their email
            # No password — they use Google to login
        )

        logger.info("New user created via Google OAuth", extra={
            'user_id': user.id,
            'email': email,
        })

        return user, True


# accounts/oauth_views.py — add this temporarily

class GoogleOAuthDebugView(APIView):
    """
    TEMPORARY — only for development debugging
    Remove before production

    Helps you see exactly what Google returns
    so you know the right field names
    """

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'code required'})

        # Exchange code
        import requests as req
        token_response = req.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                'client_secret': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                'redirect_uri': settings.GOOGLE_REDIRECT_URI,
                'grant_type': 'authorization_code',
            }
        )

        tokens = token_response.json()

        if 'access_token' not in tokens:
            return Response({'error': 'token exchange failed', 'detail': tokens})

        # Get user info
        user_response = req.get(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'}
        )

        # Return raw Google response so you can see all fields
        return Response({
            'tokens_keys': list(tokens.keys()),
            'user_info': user_response.json(),
        })