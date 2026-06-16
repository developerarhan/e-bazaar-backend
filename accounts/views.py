import logging
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from celery import shared_task

from .serializers import RegisterSerializer, LoginSerializer, ProfileSerializer
from .cookies import set_auth_cookies, clear_auth_cookies
from .tasks import send_verification_email_task
from .models import User


logger = logging.getLogger('accounts')



class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning("Registration failed", extra={
                "errors": serializer.errors,
            })
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user = serializer.save()
        # user.is_active = False at this point

        # Send verification email in background
        transaction.on_commit(
            lambda: send_verification_email_task.delay(user.id)
        )

        logger.info("User registered, verification email queued", extra={
            "user_id": user.id,
        })
        
        response = Response({
            "message": "Account created. Please check your email to verify your account.",
            "email": user.email,
        }, status=status.HTTP_201_CREATED)

        return response
    

class VerifyEmailView(APIView):
    """
    Called when user clicks the link in their email.
    Frontend reads token from URL, sends it here.
    """

    def post(self, request):
        token_str = request.data.get("token", "").strip()

        if not token_str:
            return Response(
                {"error": "Token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            uuid.UUID(token_str)
        except (ValueError, AttributeError):
            logger.warning("Email verification with malformed token", extra={
                'token': token_str[:20],  # truncate — don't log full junk
                'ip': request.META.get('REMOTE_ADDR'),
            })
            return Response(
                {'error': 'Invalid or expired verification link.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import EmailVerificationToken

            token = EmailVerificationToken.objects.select_related('user').get(
                token=token_str
            )

        except EmailVerificationToken.DoesNotExist:
            logger.warning("Invalid verification token used", extra={
                "token": token_str,
                "ip": request.META.get("REMOTE_ADDR"),
            })
            return Response(
                {"error": "Invalid verification link"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already used
        if token.is_used:
            return Response(
                {"error": "This link has already been used. Please log in."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if expired
        if not token.is_valid():
            return Response(
                {
                    "error": "This link has expired.",
                    "code": "token_expired",
                    # Frontend can show "Resend verification email" button
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        # Everything valid — activate the user
        user = token.user
        user.is_active = True
        user.save(update_fields=['is_active'])

        # Mark token as used so it can't be reused
        token.is_used = True
        token.save(update_fields=['is_used'])

        # Now issue tokens — user is verified and can log in
        refresh = RefreshToken.for_user(user)

        logger.info("Email verified successfully", extra={
            "user_id": user.id,
            "email": user.email,
        })

        response = Response({
            "message": "Email verified successfully. Welcome to E-Bazaar!",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
            }
        }, status=status.HTTP_200_OK)

         # Log them in immediately after verification
        set_auth_cookies(
            response,
            access_token=str(refresh.access_token),
            refresh_token=str(refresh),
        )

        return response


class ResendVerificationView(APIView):
    """
    For users whose token expired before they could verify.
    """

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)

            if user.is_active:
                return Response(
                    {"message": "This account is already verified."},
                    status=status.HTTP_200_OK
                )
            
            # Queue new verification email
            print(f"email sent - {user.id}")
            send_verification_email_task.delay(user.id)

            logger.info("Verification email resent", extra={
                "user_id": user.id,
            })

        except User.DoesNotExist:
            # Don't reveal whether email exists — security
            pass

        # Always return the same response
        # Prevents user enumeration attacks
        return Response({
            "message": "If that email exists, a new verification link has been sent."
        }, status=status.HTTP_200_OK)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning("Login failed - invalid credentials", extra={
                "email": request.data.get("email", "not_provided"),
                "ip": request.META.get("REMOTE_ADDR"),
            })
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        
        logger.info("User logged in", extra={
                "user_id": user.id,
                "ip": request.META.get("REMOTE_ADDR"),
                # Never log passwords. Be careful with emails in logs
                # depending on your privacy policy.
            })

        response =  Response({
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "phone": user.phone,
                },
                # Notice: NO tokens in the response body
                # They go into cookies only
            }, status=status.HTTP_200_OK)
        
        set_auth_cookies(
            response,
            access_token=str(refresh.access_token),
            refresh_token=str(refresh),
        )

        return response   
    

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Blacklist the refresh token so it can't be reused
        # even if someone copied the cookie before logout
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()

                logger.info("User logged out", extra={
                    "user_id": request.user.id,
                })
        
            except TokenError:
                # Token already invalid — still proceed with logout
                logger.warning("Logout with invalid refresh token", extra={
                    "user_id": request.user.id,
                })

        response = Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK
        )

        # Clear both cookies from the browser
        clear_auth_cookies(response)

        return response
        

class TokenRefreshView(APIView):
    """
    Called automatically by the frontend when access token expires.
    Reads the refresh token from cookie, issues new token pair.
    This is where rotation happens.
    """

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)

        if not refresh_token:
            logger.warning("Token refresh attempted with no refresh cookie", extra={
                "ip": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT")
            })
            return Response(
             {"detail": "Refresh token not found", "code": "refresh_token_missing"},
                status=status.HTTP_401_UNAUTHORIZED   
            )
        
        try:
            # SimpleJWT validates the refresh token
            refresh = RefreshToken(refresh_token)

            # ↑ If ROTATE_REFRESH_TOKENS=True in settings,
            # calling refresh.access_token automatically:
            # 1. Generates a new access token
            # 2. Generates a new refresh token
            # 3. Blacklists the old refresh token

            new_access_token = str(refresh.access_token)
            new_refresh_token = str(refresh)

            logger.info("Token refreshed successfully", extra={
                "user_id": refresh.payload.get("user_id"),
            })

            response = Response(
                {"message": "Token refreshed"},
                status=status.HTTP_200_OK
            )

            # Set the new token pair as cookies
            set_auth_cookies(
                response,
                access_token=new_access_token,
                refresh_token=new_refresh_token,
            )

            return response
        
        except TokenError as e:
            # Refresh token is expired, invalid, or already used
            # This is where reuse detection happens
            logger.warning("Invalid refresh token used", extra={
                "error": str(e),
                "ip": request.META.get("REMOTE_ADDR"),
            })            

            response = Response(
                {
                    "detail": "Refresh token is invalid or expired",
                    "code": "refresh_token_invalid",
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

            # Clear cookies — force user to log in again
            clear_auth_cookies(response)

            return response

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        serilaizer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serilaizer.is_valid():
            serilaizer.save()
            return Response({
                "message": "Profile Updated",
                "data": serilaizer.data
            })
        
        return Response(serilaizer.errors, status=status.HTTP_400_BAD_REQUEST)