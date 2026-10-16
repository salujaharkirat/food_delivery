from django.urls import path

from .views import OrderList, update_order_status, OrderDetail, RestaurantList, RestaurantDetail, MealList, MealDetail

urlpatterns = [
  path("restaurants/", RestaurantList.as_view()),
  path("restaurants/<int:restaurant_id>/", RestaurantDetail.as_view()),
  path("restaurants/<int:restaurant_id>/meals/", MealList.as_view()),
  path("restaurants/<int:restaurant_id>/meals/<int:meal_id>/", MealDetail.as_view()),
  path("orders/", OrderList.as_view()),
  path("orders/<int:order_id>/status/", update_order_status),
  path("orders/<int:order_id>/", OrderDetail.as_view()),
]
