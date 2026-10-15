from django.urls import path

from .views import get_restaurants, get_meals, place_order, update_order_status

urlpatterns = [
  path("restaurants/", get_restaurants),
  path("restaurants/<int:restaurant_id>/meals/", get_meals),
  path("orders/", place_order),
  path("orders/<int:order_id>/status/", update_order_status)
]
