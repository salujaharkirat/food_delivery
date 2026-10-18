from rest_framework.permissions import BasePermission

from .models import Role


class DenyAll(BasePermission):
  def has_permission(self, request, view):
    return False

class RoleMethodMixin:
  permission_map = {}
  def get_permissions(self):
    roles = self.permission_map.get(
      self.request.method,[DenyAll]
    )
    return [role() for role in roles]


class BaseRole(BasePermission):
  allowed_roles = ()

  def has_permission(self, request, view):
    user = request.user
    return bool(user and user.is_authenticated and user.role in self.allowed_roles)

class IsCustomer(BaseRole):
  allowed_roles = (Role.CUSTOMER,)
  message = "Only customer can perform this action"

class IsOwner(BaseRole):
  allowed_roles = (Role.OWNER, )
  message = "Only owner can perform this action"

class IsCustomerOrOwner(BaseRole):
  allowed_roles = (Role.OWNER, Role.CUSTOMER,)
  message = "Only customers or owner can perform this action"

class IsAdmin(BaseRole):
  allowed_roles = (Role.ADMIN,)
  message = "Only admin can perform this action"
