from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status
from typing import cast

from user.permissions import IsAdmin
from user.models import User

from .serializers import AdminUserListSerializer, AdminUserCreateSerializer

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
    return self.paginated_response(request, users, AdminUserListSerializer)


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