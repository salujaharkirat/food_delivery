from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class SafeJWTAuthentication(JWTAuthentication):
  def get_user(self, validated_token):
    user = super().get_user(validated_token)

    if user and user.is_blocked:
      raise AuthenticationFailed("This account is blocked")

    return user
