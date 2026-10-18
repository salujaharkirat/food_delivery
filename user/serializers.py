from rest_framework import serializers
from .models import Role, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


class RegisterSerializer(serializers.Serializer):
  email = serializers.EmailField(max_length=255)
  password = serializers.CharField(write_only=True, style={"input_type": "password"})
  role = serializers.ChoiceField(choices=[Role.CUSTOMER, Role.OWNER])

  def validate_email(self, value):
    email = value.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
      raise serializers.ValidationError(f"A user with {email} already exists")

    return email

  def validate_password(self, value):
    try:
      validate_password(value)
    except DjangoValidationError as e:
      raise serializers.ValidationError(e.messages)

    return value


  def create(self, validated_data):
    return User.objects.create_user(**validated_data)

class LoginSerializer(serializers.Serializer):
  email = serializers.EmailField(max_length=255)
  password = serializers.CharField(write_only=True, style={"input_type": "password"})
