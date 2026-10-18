from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from user.models import User, Role
from user.serializers import RegisterSerializer


class AdminUserSerializer(serializers.ModelSerializer):
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

class AdminUserUpdateSerializer(serializers.ModelSerializer):
  email = serializers.EmailField(max_length=255)
  password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
  role = serializers.ChoiceField(choices=Role.choices)

  class Meta:
    model = User
    fields = ('email', 'password', 'role', 'is_active', 'is_blocked')

  def validate_email(self, value):
    email = value.strip().lower()
    if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
      raise serializers.ValidationError(f"A user with {email} already exists")
    return email

  def validate_password(self, value):
    try:
      validate_password(value, user=self.instance)
    except DjangoValidationError as e:
      raise serializers.ValidationError(e.messages)
    return value

  def validate_role(self, value):
    request = self.context.get("request")
    actor_is_builtin = bool(request and getattr(request.user, "is_builtin", False))

    if value == Role.ADMIN and not actor_is_builtin:
      raise PermissionDenied("Only the built-in admin can make someone an admin.")
    return value

  def validate(self, attrs):
    user = self.instance

    if user.is_builtin:
      raise PermissionDenied("The built-in admin cannot be updated")

    return attrs

  def update(self, instance, validated_data):
    password = validated_data.pop("password", None)
    for field, value in validated_data.items():
      setattr(instance, field, value)
    if password:
      instance.set_password(password)
    instance.save()
    return instance