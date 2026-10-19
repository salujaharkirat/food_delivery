from decimal import Decimal
from datetime import timedelta

from rest_framework.test import APITestCase
from django.utils import timezone
from django.test import override_settings

from user.models import User, Role
from food_delivery.models import Restaurant, Meal, Coupon, \
Order, OrderStatus, OrderItem, OrderStatusHistory

PASSWORD = "Str0ng!pass#92"
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BaseAPITestCase(APITestCase):
  password = PASSWORD


  ################ DATA ###############
  def make_user(self, email, role = Role.CUSTOMER, **extra):
    return User.objects.create_user(email=email, password=self.password, role=role, **extra)

  def make_owner(self, email="owner@test.com", **extra):
    return self.make_user(email, Role.OWNER, **extra)

  def make_admin(self, email="admin@test.com"):
    return User.objects.create_superuser(email=email, password=self.password, is_builtin=True)

  def make_restaurant(self, owner, name="Pizza place", **extra):
    return Restaurant.objects.create(name=name, description="Good food", owner=owner, **extra)

  def make_meal(self, restaurant, name="Margherita", price="10.00", **extra):
    return Meal.objects.create(restaurant=restaurant, name=name, description="Tasty", price=Decimal(price), **extra)

  def make_coupon(self, code="SAVE10", percentage="10", expires_in=timedelta(days=30), **extra):
    return Coupon.objects.create(
      code=code, discount_percentage=Decimal(percentage), expires_at=timezone.now() + expires_in, **extra
    )

  def make_order(self, customer, restaurant, meals_and_quantities, status=OrderStatus.PLACED):
    # Builds an order directly in the DB (fast, any status); use the API when the order flow itself is under test.
    subtotal = sum((meal.price * quantity for meal, quantity in meals_and_quantities), Decimal("0.00"))
    order = Order.objects.create(
      restaurant=restaurant, customer=customer, status=status, subtotal=subtotal, total_amount=subtotal
    )
    OrderItem.objects.bulk_create([
      OrderItem(order=order, meal=meal, quantity=quantity, unit_price=meal.price)
      for meal, quantity in meals_and_quantities
    ])
    OrderStatusHistory.objects.create(order=order, status=OrderStatus.PLACED, changed_by=customer)
    return order

  ################# AUTH ################
  def login(self, user):
    response = self.client.post("/api/auth/login/", {"email": user.email, "password": self.password}, format="json")
    self.assertEqual(response.status_code, 200)
    return response.data["tokens"]["access_token"]

  def auth_as(self, user):
    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.login(user)}")
