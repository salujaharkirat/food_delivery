from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.shortcuts import get_object_or_404
from typing import cast

from user.models import User, Role


from .models import Restaurant, Meal, Order
from .serializers import RestaurantSerializer, MealSerializer, OrderSerializer, OrderOutputSerializer, OrderStatusSerializer, OrderDetailOutputSerializer
from .service import create_order, change_order_status


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

class OrderList(APIView):
  def get(self, request):
    user = cast(User, request.user)

    paginator = PageNumberPagination()

    if user.role == Role.CUSTOMER:
      orders = Order.objects.filter(customer=user)
    elif user.role == Role.OWNER:
      orders = Order.objects.filter(restaurant__owner=user)
    else:
      return Response({"message": "Only customers and owners can view the orders"}, status=status.HTTP_403_FORBIDDEN)


    page = paginator.paginate_queryset(orders, request)
    return paginator.get_paginated_response(OrderOutputSerializer(page, many=True).data)

  def post(self, request):
    user = cast(User, request.user)
    
    if user.role != Role.CUSTOMER:
      return Response({"message": "Only customers can place orders"}, status=status.HTTP_403_FORBIDDEN)
  
    serializer = OrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order = create_order(user, serializer.validated_data)
  
    return Response(OrderOutputSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetail(APIView):
  def get(self, request, order_id):
    user = cast(User, request.user)

    if user.role == Role.CUSTOMER:
      order = get_object_or_404(Order, id=order_id, customer=user)
    elif user.role == Role.OWNER:
      order = get_object_or_404(Order, id=order_id, restaurant__owner=user)
    else:
      return Response({"message": "Only customers and owners can view the order"}, status=status.HTTP_403_FORBIDDEN)

    return Response(OrderDetailOutputSerializer(order).data, status=status.HTTP_200_OK)

@api_view(['POST'])
def update_order_status(request, order_id):
  user = cast(User, request.user)

  if user.role not in (Role.CUSTOMER, Role.OWNER):
    return Response({"message": "Only customer and owners can update status"}, status=status.HTTP_403_FORBIDDEN)

  serializer = OrderStatusSerializer(data=request.data)
  serializer.is_valid(raise_exception=True)
  order = change_order_status(request.user, order_id, serializer.validated_data["status"]) # type: ignore

  return Response(OrderOutputSerializer(order).data, status=status.HTTP_200_OK)
  
  

