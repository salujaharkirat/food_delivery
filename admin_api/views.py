from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework import status
from typing import cast
from django.shortcuts import get_object_or_404

from user.permissions import IsAdmin
from user.models import User
from user.serializers import RegisterSerializer

from .serializers import AdminUserSerializer, \
AdminUserUpdateSerializer, AdminRestaurantSerializer, \
AdminRestaurantCreateSerializer, AdminRestaurantUpdateSerializer, \
AdminMealSerializer, AdminMealCreateSerializer, AdminMealUpdateSerializer

from food_delivery.models import Restaurant, Meal

class AdminAPIView(APIView):
  permission_classes = [IsAdmin]

  def paginated_response(self, request, data, serializer):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(data, request)
    return paginator.get_paginated_response(serializer(page, many=True).data)


class AdminUsersList(AdminAPIView):
  def get(self, request):

    users = User.objects.order_by('id')
    return self.paginated_response(request, users, AdminUserSerializer)


  def post(self, request):
    serializer = RegisterSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)

    user = cast(User, serializer.save())

    payload = {
      "detail": "User created successfully",
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

    user.is_active = False
    user.save(update_fields=["is_active"])

    return Response({"detail": "User deleted successfully"}, status=status.HTTP_200_OK)

class AdminRestaurantsList(AdminAPIView):
  def get(self, request):
    restaurants = Restaurant.objects.select_related("owner").order_by("id")
    return self.paginated_response(request, restaurants, AdminRestaurantSerializer)

  def post(self, request):
    serializer = AdminRestaurantCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    restaurant = serializer.save()

    return Response(AdminRestaurantSerializer(restaurant).data, status=status.HTTP_201_CREATED)

class AdminRestaurantsDetail(AdminAPIView):
  def get(self, request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    return Response(AdminRestaurantSerializer(restaurant).data, status=status.HTTP_200_OK)

  def _update(self, request, restaurant_id, partial):
    queryset = Restaurant.objects.select_related("owner")
    restaurant = get_object_or_404(queryset, id=restaurant_id)

    serializer = AdminRestaurantUpdateSerializer(restaurant, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)

    updated_restaurant = serializer.save()

    return Response(AdminRestaurantSerializer(updated_restaurant).data, status=status.HTTP_200_OK)


  def patch(self, request, restaurant_id):
    return self._update(request, restaurant_id, True)

  def put(self, request, restaurant_id):
    return self._update(request, restaurant_id, False)

  def delete(self, request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)

    if not restaurant.is_active:
      raise NotFound("Restaurant is already deleted")

    restaurant.is_active = False
    restaurant.save(update_fields=("is_active",))

    return Response({"detail": "Restaurant deleted successfully"}, status=status.HTTP_200_OK)


class AdminMealsList(AdminAPIView):
  def get(self, request):
    meals = Meal.objects.select_related("restaurant").order_by("id")
    return self.paginated_response(request, meals, AdminMealSerializer)

  def post(self, request):
    serializer = AdminMealCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    meal = serializer.save()

    return Response(AdminMealSerializer(meal).data, status=status.HTTP_201_CREATED)

class AdminMealsDetail(AdminAPIView):
  def get(self, request, meal_id):
    queryset = Meal.objects.select_related("restaurant")
    meal = get_object_or_404(queryset, id=meal_id)

    return Response(AdminMealSerializer(meal).data, status=status.HTTP_200_OK)

  def _update(self, request, meal_id, partial):
    queryset = Meal.objects.select_related("restaurant")
    meal = get_object_or_404(queryset, id=meal_id)

    serializer = AdminMealUpdateSerializer(meal, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    new_meal = serializer.save()

    return Response(AdminMealSerializer(new_meal).data, status=status.HTTP_200_OK)


  def put(self, request, meal_id):
    return self._update(request, meal_id, False)

  def patch(self, request, meal_id):
    return self._update(request, meal_id, True)

  def delete(self, request, meal_id):
    meal = get_object_or_404(Meal, id=meal_id)

    if not meal.is_active:
      raise NotFound("Meal is already deleted")

    meal.is_active = False
    meal.save(update_fields=("is_active",))

    return Response({"detail": "Meal deleted successfully"}, status=status.HTTP_200_OK)
