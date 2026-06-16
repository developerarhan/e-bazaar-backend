from django.conf import settings


def set_auth_cookies(response, access_token, refresh_token):
    """
    Helper function — sets both tokens as HttpOnly cookies.
    Called after login and after token refresh.
    Centralizing this means you change cookie settings in one place.
    """

    # Access token cookie — short lived
    response.set_cookie(
        key=settings.AUTH_COOKIE,
        value=str(access_token),
        max_age=settings.AUTH_COOKIE_MAX_AGE,
        httponly=settings.AUTH_COOKIE_HTTP_ONLY,     # JS cannot read this
        secure=settings.AUTH_COOKIE_SECURE,  # HTTPS only in production, HTTP ok in dev
        samesite=settings.AUTH_COOKIE_SAMESITE,      # CSRF protection
        path=settings.AUTH_COOKIE_PATH,
    )

    response.set_cookie(
        key=settings.AUTH_COOKIE_REFRESH,
        value=str(refresh_token),
        max_age=settings.AUTH_COOKIE_REFRESH_MAX_AGE,
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=settings.AUTH_COOKIE_HTTP_ONLY,
        path=settings.AUTH_COOKIE_REFRESH_PATH,   # ← restricted path
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )

    return response

def clear_auth_cookies(response):
    """
    Deletes both cookies.
    Called on logout.
    Setting max_age=0 tells the browser to delete immediately.
    """
    response.delete_cookie(
        key=settings.AUTH_COOKIE,
        path=settings.AUTH_COOKIE_PATH,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )

    response.delete_cookie(
        key=settings.AUTH_COOKIE_REFRESH,
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )

    return response
