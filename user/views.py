from rest_framework.decorators import api_view, permission_classes, \
authentication_classes
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from typing import cast

from .serializers import RegisterSerializer, LoginSerializer
from .models import User


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def register(request):
  serializer = RegisterSerializer(data=request.data)
  serializer.is_valid(raise_exception=True)

  user = cast(User, serializer.save())
  refresh = RefreshToken.for_user(user)

  payload = {
    "message": f"User created successfully",
    "user": {
      "id": user.id,
      "email": user.email,
      "role": user.role
    },
    "tokens": {
      "access_token": str(refresh.access_token),
      "refresh_token": str(refresh)
    }
  }

  return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login(request):
  serializer = LoginSerializer(data=request.data)
  serializer.is_valid(raise_exception=True)

  user = authenticate(
    request,
    email=serializer.validated_data["email"],
    password=serializer.validated_data["password"]
  )

  if user is None:
    return Response({"message": "Invalid email or password"}, status=status.HTTP_400_BAD_REQUEST)

  user = cast(User, user)

  if user.is_blocked:
    return Response({"message": "User is blocked"}, status=status.HTTP_403_FORBIDDEN)

  refresh = RefreshToken.for_user(user)

  payload = {
    "message": "Login successful",
    "user": {
      "id": user.pk,
      "email": user.email,
      "role": user.role
    },
    "tokens": {
      "access_token": str(refresh.access_token),
      "refresh_token": str(refresh)
    }
  }

  return Response(payload, status=status.HTTP_200_OK)
