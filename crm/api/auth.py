from datetime import timedelta
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

TOKEN_LIFETIME = timedelta(days=7)


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token.created + TOKEN_LIFETIME <= timezone.now():
            raise AuthenticationFailed('Token muddati tugagan. Qayta kiring.')
        return user, token
