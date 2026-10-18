from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from user.models import User, Role
from user.serializers import RegisterSerializer


class AdminUserListSerializer(serializers.ModelSerializer):
  class Meta:
    model = User
    fields = ('id', 'last_login', 'is_active', 'is_blocked', 'is_builtin', 'date_joined', 'email', 'role', 'created_at')

class AdminUserCreateSerializer(RegisterSerializer):
  role = serializers.ChoiceField(choices=Role.choices)

  def validate_role(self, value):
    request = self.context.get("request")
    actor_is_builtin = bool(request and getattr(request.user, "is_builtin", False))

    if value == Role.ADMIN and not actor_is_builtin:
      raise PermissionDenied("Only a built-in/super admin can create admins.")

    return value