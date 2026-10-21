from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

ACCESS_COOKIE = 'access_token'
REFRESH_COOKIE = 'refresh_token'


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate from an HttpOnly access-token cookie, still allowing Bearer headers."""

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            try:
                result = super().authenticate(request)
                if result is not None:
                    return result
            except (InvalidToken, AuthenticationFailed):
                if not request.COOKIES.get(ACCESS_COOKIE):
                    raise

        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if not raw_token:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


def _cookie_kwargs(path, max_age):
    return {
        'max_age': max_age,
        'httponly': True,
        'secure': not settings.DEBUG,
        'samesite': 'Lax',
        'path': path,
    }


def set_auth_cookies(response, access=None, refresh=None):
    if access:
        lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        response.set_cookie(
            ACCESS_COOKIE,
            access,
            **_cookie_kwargs('/', int(lifetime.total_seconds())),
        )
    if refresh:
        lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            **_cookie_kwargs('/api/accounts/', int(lifetime.total_seconds())),
        )
    return response


def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path='/')
    response.delete_cookie(REFRESH_COOKIE, path='/api/accounts/')
    return response
