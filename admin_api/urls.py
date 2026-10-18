from django.urls import path

from .views import AdminUsersList, AdminUsersDetail, AdminRestaurantsList,\
AdminRestaurantsDetail, AdminMealsList, AdminMealsDetail

urlpatterns = [
  path("users/", AdminUsersList.as_view()),
  path("users/<int:user_id>/", AdminUsersDetail.as_view()),
  path("restaurants/",AdminRestaurantsList.as_view()),
  path("restaurants/<int:restaurant_id>/",AdminRestaurantsDetail.as_view()),
  path("meals/",AdminMealsList.as_view()),
  path("meals/<int:meal_id>/",AdminMealsDetail.as_view())
]