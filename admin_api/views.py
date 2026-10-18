from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework import status
from typing import cast
from django.shortcuts import get_object_or_404

from user.permissions import IsAdmin
from user.models import User, Role

from .serializers import AdminUserSerializer, AdminUserCreateSerializer, \
AdminUserUpdateSerializer

class AdminAPIView(APIView):
  permission_classes = [IsAdmin]

  def paginated_response(self, request, data, serializer):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(data, request)
    return paginator.get_paginated_response(serializer(page, many=True).data)
    
    

# Create your views here.
class AdminUsersList(AdminAPIView):
  def get(self, request):

    users = User.objects.order_by('id')
    return self.paginated_response(request, users, AdminUserSerializer)


  def post(self, request):
    serializer = AdminUserCreateSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    user = cast(User, serializer.save())

    payload = {
      "message": f"User created successfully",
      "user": {
        "id": user.id,
        "email": user.email,
        "role": user.role
      },
    }

    return Response(payload, status=status.HTTP_201_CREATED)

class AdminUsersDetail(AdminAPIView):
  def get(self, request, user_id):
    user = get_object_or_404(User, id=user_id)

    return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)

  def _update(self, request, user_id, partial):
    user = get_object_or_404(User, id=user_id)

    if user.role == Role.ADMIN and not request.user.is_builtin:
      raise PermissionDenied("Only the built-in admin can update admins")

    serializer = AdminUserUpdateSerializer(user, data=request.data, partial=partial, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response(AdminUserSerializer(user).data, status=status.HTTP_200_OK)

  def put(self, request, user_id):
    return self._update(request, user_id, False)

  def patch(self, request, user_id):
    return self._update(request, user_id, True)

  def delete(self, request, user_id):
    user = get_object_or_404(User, id=user_id)

    if not user.is_active:
      raise NotFound("User is already deleted")

    if user.is_builtin:
      raise PermissionDenied("Built in user cannot be deleted")

    if user.role == Role.ADMIN and not request.user.is_builtin:
      raise PermissionDenied("Only the built-in admin can delete admins")

    user.is_active = False
    user.save(update_fields=["is_active"])

    return Response({"message": "User deleted successfully"}, status=status.HTTP_200_OK)