from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager

class Role(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    OWNER = "owner", "Restaurant Owner"
    ADMIN = "admin", "Administrator"


class UserManager(BaseUserManager):
  use_in_migrations = True

  def _create_user(self, email, password, **extra_fields):
    if not email:
      raise ValueError("Email is required")
    email = self.normalize_email(email).lower()
    user = self.model(email=email, **extra_fields)
    user.set_password(password)
    user.save(using=self._db)
    return user

  def create_user(self, email, password, **extra_fields):
    extra_fields.setdefault("role", Role.CUSTOMER)
    extra_fields.setdefault("is_staff", False)
    extra_fields.setdefault("is_superuser", False)
    return self._create_user(email, password, **extra_fields)

  def create_superuser(self, email, password, **extra_fields):
    extra_fields.setdefault("role", Role.ADMIN)
    extra_fields.setdefault("is_staff", True)
    extra_fields.setdefault("is_superuser", True)
    return self._create_user(email, password, **extra_fields)
   

class User(AbstractUser):
  username = None
  email = models.EmailField(unique=True, max_length=255)
  role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
  is_blocked = models.BooleanField(default=False)
  is_builtin = models.BooleanField(default=False)   # built-in admin, cannot be deleted
  created_at = models.DateTimeField(auto_now_add=True)

  USERNAME_FIELD = "email"
  REQUIRED_FIELDS = []

  objects = UserManager()   # type: ignore[assignment]

  def __str__(self):
    return self.email

  def delete(self, *args, **kwargs):
    if self.is_builtin:
       raise PermissionError("The built-in admin account cannot be deleted")
    return super().delete(*args, **kwargs)