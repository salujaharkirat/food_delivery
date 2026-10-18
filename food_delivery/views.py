from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.shortcuts import get_object_or_404

from typing import cast

from user.models import User, Role
from user.permissions import IsCustomerOrOwner, IsCustomer, IsOwner, RoleMethodMixin

from .models import Restaurant, Order, Meal
from .serializers import RestaurantSerializer, OrderSerializer, OrderOutputSerializer, \
OrderStatusSerializer, OrderDetailOutputSerializer, RestaurantInputSerializer, \
OwnerRestaurantSerializer, OwnerMealSerializer, MealInputSerializer, MealSerializer
from .service import create_order, change_order_status
from .db_utils import get_visible_restaurants

class OrderList(RoleMethodMixin, APIView):
  permission_map = {
    "GET": [IsCustomerOrOwner],
    "POST": [IsCustomer],
  }

  def get(self, request):
    user = cast(User, request.user)

    paginator = PageNumberPagination()

    if user.role == Role.CUSTOMER:
      orders = Order.objects.prefetch_related('items').filter(customer=user)
    elif user.role == Role.OWNER:
      orders = Order.objects.prefetch_related('items').filter(restaurant__owner=user)

    page = paginator.paginate_queryset(orders, request)
    return paginator.get_paginated_response(OrderOutputSerializer(page, many=True).data)

  def post(self, request):
    user = cast(User, request.user)
    serializer = OrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order = create_order(user, serializer.validated_data)

    return Response(OrderOutputSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetail(RoleMethodMixin, APIView):
  permission_map = {
    "GET": [IsCustomerOrOwner]
  }

  def get(self, request, order_id):
    user = cast(User, request.user)

    if user.role == Role.CUSTOMER:
      order = get_object_or_404(Order, id=order_id, customer=user)
    elif user.role == Role.OWNER:
      order = get_object_or_404(Order, id=order_id, restaurant__owner=user)

    return Response(OrderDetailOutputSerializer(order).data, status=status.HTTP_200_OK)

class RestaurantList(RoleMethodMixin, APIView):
  permission_map = {
    "GET": [IsCustomerOrOwner],
    "POST": [IsOwner]
  }

  def get(self, request):
    user = cast(User, request.user)

    paginator = PageNumberPagination()

    if user.role == Role.CUSTOMER:
      restaurants = get_visible_restaurants()
    elif user.role == Role.OWNER:
      restaurants = Restaurant.objects.filter(owner=user, is_active=True, is_blocked=False)

    page = paginator.paginate_queryset(restaurants, request)
    return paginator.get_paginated_response(RestaurantSerializer(page, many=True).data)


  def post(self, request):
    user = cast(User, request.user)

    serializer = RestaurantInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    restaurant = Restaurant.objects.create(
      description=serializer.validated_data["description"],
      name=serializer.validated_data["name"],
      owner=user
    )

    return Response(RestaurantSerializer(restaurant).data, status=status.HTTP_201_CREATED)

class RestaurantDetail(RoleMethodMixin, APIView):
  permission_map = {
    "GET": [IsCustomerOrOwner],
    "POST": [IsOwner],
    "PUT": [IsOwner],
    "PATCH": [IsOwner],
    "DELETE": [IsOwner]
  }

  def get(self, request, restaurant_id):
    user = cast(User, request.user)

    if user.role == Role.CUSTOMER:
      restaurant = get_object_or_404(get_visible_restaurants(), id=restaurant_id)
      return Response(RestaurantSerializer(restaurant).data, status=status.HTTP_200_OK)
    elif user.role == Role.OWNER:
      restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True, owner=user)
      return Response(OwnerRestaurantSerializer(restaurant).data, status=status.HTTP_200_OK)

  def _update(self, request, restaurant_id, partial):
    user = cast(User, request.user)

    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True, owner=user)

    if restaurant.is_blocked:
      return Response({"detail": "This restaurant is blocked by an administrator"}, status=status.HTTP_403_FORBIDDEN)

    serializer = RestaurantInputSerializer(restaurant, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    updated_restaurant = serializer.save()

    return Response(OwnerRestaurantSerializer(updated_restaurant).data, status=status.HTTP_200_OK)


  def put(self, request, restaurant_id):
    return self._update(request, restaurant_id, partial=False)

  def patch(self, request, restaurant_id):
    return self._update(request, restaurant_id, partial=True)

  def delete(self, request, restaurant_id):
    user = cast(User, request.user)

    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True, owner=user)

    if restaurant.is_blocked:
      return Response({"detail": "This restaurant is blocked by an administrator"}, status=status.HTTP_403_FORBIDDEN)

    restaurant.is_active = False
    restaurant.save(update_fields=["is_active"])

    return Response({"detail": "Restaurant deleted successfully"}, status=status.HTTP_200_OK)

class MealList(RoleMethodMixin, APIView):
  permission_map = {
    "GET": [IsCustomerOrOwner],
    "POST": [IsOwner]
  }

  def get(self, request, restaurant_id):
    user = cast(User, request.user)

    paginator = PageNumberPagination()

    if user.role == Role.CUSTOMER:
      get_object_or_404(get_visible_restaurants(), id=restaurant_id)
      meals = Meal.objects.filter(restaurant_id=restaurant_id, is_active=True, is_blocked=False)
      serializer_class = MealSerializer
    elif user.role == Role.OWNER:
      get_object_or_404(Restaurant, id=restaurant_id, is_active=True, owner=user)
      meals = Meal.objects.filter(restaurant_id=restaurant_id, is_active=True)
      serializer_class = OwnerMealSerializer

    page = paginator.paginate_queryset(meals, request)
    return paginator.get_paginated_response(serializer_class(page, many=True).data)

  def post(self, request, restaurant_id):
    user = cast(User, request.user)

    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True, owner=user)

    if restaurant.is_blocked:
      return Response({"detail": "This restaurant is blocked by an administrator"}, status=status.HTTP_403_FORBIDDEN)

    serializer = MealInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    meal = serializer.save(restaurant=restaurant)

    return Response(OwnerMealSerializer(meal).data, status=status.HTTP_201_CREATED)


class MealDetail(RoleMethodMixin, APIView):
  permission_map = {
    "GET": [IsCustomerOrOwner],
    "POST": [IsOwner],
    "PUT": [IsOwner],
    "PATCH": [IsOwner],
    "DELETE": [IsOwner]
  }

  def get(self, request, restaurant_id, meal_id):
    user = cast(User, request.user)

    if user.role == Role.CUSTOMER:
      meal = get_object_or_404(
        Meal, id=meal_id, restaurant_id=restaurant_id, is_active=True, is_blocked=False,
        restaurant__is_active=True, restaurant__is_blocked=False,
        restaurant__owner__is_active=True, restaurant__owner__is_blocked=False
      )
      return Response(MealSerializer(meal).data, status=status.HTTP_200_OK)
    elif user.role == Role.OWNER:
      meal = get_object_or_404(
        Meal, id=meal_id, restaurant_id=restaurant_id, is_active=True,
        restaurant__is_active=True, restaurant__owner=user
      )
      return Response(OwnerMealSerializer(meal).data, status=status.HTTP_200_OK)

  def _get_editable_meal(self, user, restaurant_id, meal_id):
    meal = get_object_or_404(
      Meal.objects.select_related("restaurant"), id=meal_id, restaurant_id=restaurant_id, is_active=True,
      restaurant__is_active=True, restaurant__owner=user
    )

    if meal.is_blocked or meal.restaurant.is_blocked:
      return meal, Response({"detail": "This meal or its restaurant is blocked by an administrator"},
                            status=status.HTTP_403_FORBIDDEN)
    return meal, None

  def _update(self, request, restaurant_id, meal_id, partial):
    user = cast(User, request.user)

    meal, blocked = self._get_editable_meal(user, restaurant_id, meal_id)
    if blocked:
      return Response({"detail": "Meal is blocked by the admin"}, status=status.HTTP_403_FORBIDDEN)

    serializer = MealInputSerializer(meal, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    updated_meal = serializer.save()

    return Response(OwnerMealSerializer(updated_meal).data, status=status.HTTP_200_OK)


  def put(self, request, restaurant_id, meal_id):
    return self._update(request, restaurant_id, meal_id, partial=False)

  def patch(self, request, restaurant_id, meal_id):
    return self._update(request, restaurant_id, meal_id, partial=True)

  def delete(self, request, restaurant_id, meal_id):
    user = cast(User, request.user)

    meal, blocked = self._get_editable_meal(user, restaurant_id, meal_id)

    if blocked:
      return Response({"detail": "Meal is blocked by the admin"}, status=status.HTTP_403_FORBIDDEN)

    meal.is_active = False
    meal.save(update_fields=["is_active"])

    return Response({"detail": "Meal deleted successfully"}, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsCustomerOrOwner])
def update_order_status(request, order_id):
  serializer = OrderStatusSerializer(data=request.data)
  serializer.is_valid(raise_exception=True)
  order = change_order_status(request.user, order_id, serializer.validated_data["status"]) # type: ignore

  return Response(OrderOutputSerializer(order).data, status=status.HTTP_200_OK)
