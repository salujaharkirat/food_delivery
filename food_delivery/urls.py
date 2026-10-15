from django.urls import path

from .views import get_restaurants, get_meals, OrderList, update_order_status, OrderDetail

urlpatterns = [
  path("restaurants/", get_restaurants),
  path("restaurants/<int:restaurant_id>/meals/", get_meals),
  path("orders/", OrderList.as_view()),
  path("orders/<int:order_id>/status/", update_order_status),
  path("orders/<int:order_id>/", OrderDetail.as_view()),
]
