from django.urls import path

from .views import AdminUsersList

urlpatterns = [
  path("users/", AdminUsersList.as_view())
]