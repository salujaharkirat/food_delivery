from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status
from typing import cast

from user.models import User, Role


from .models import Restaurant, Meal
from .serializers import RestaurantSerializer, MealSerializer, OrderSerializer, OrderOutputSerializer
from .service import create_order


@api_view(['GET'])
def get_restaurants(request):
  user = cast(User, request.user)
  
  if user.role != Role.CUSTOMER:
    return Response({"message": "Only customers can browse restaurants"}, status=status.HTTP_403_FORBIDDEN)

  restaurants = Restaurant\
    .objects\
    .filter(is_blocked=False, is_active=True)

  paginator = PageNumberPagination()
  page = paginator.paginate_queryset(restaurants, request)
  serializer = RestaurantSerializer(page, many=True)
  return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
def get_meals(request, restaurant_id):
  user = cast(User, request.user)

  if user.role != Role.CUSTOMER:
    return Response({"message": "Only customers can browse meals"}, status=status.HTTP_403_FORBIDDEN)

  if not restaurant_id:
    return Response({"message": "Please pass restaurant id"}, status=status.HTTP_400_BAD_REQUEST)
  
  meals = Meal.objects.filter(restaurant_id=restaurant_id, is_blocked=False, is_active=True)

  paginator = PageNumberPagination()
  page = paginator.paginate_queryset(meals, request)
  serializer = MealSerializer(page, many=True)
  return paginator.get_paginated_response(serializer.data)

@api_view(['POST'])
def place_order(request):
  user = cast(User, request.user)

  if user.role != Role.CUSTOMER:
    return Response({"message": "Only customers can place orders"}, status=status.HTTP_403_FORBIDDEN)

  serializer = OrderSerializer(data=request.data)
  serializer.is_valid(raise_exception=True)
  order = create_order(user, serializer.validated_data)

  return Response(OrderOutputSerializer(order).data, status=status.HTTP_201_CREATED)
  
  

