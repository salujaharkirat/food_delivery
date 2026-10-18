from django.urls import path

from .views import AdminUsersList, AdminUsersDetail

urlpatterns = [
  path("users/", AdminUsersList.as_view()),
  path("users/<int:user_id>/", AdminUsersDetail.as_view())
]