from decimal import Decimal

from django.db import models
from django.conf import settings
from django.db.models import Q, CheckConstraint, UniqueConstraint

class OrderStatus(models.TextChoices):
  PLACED = "placed"
  CANCELED = "canceled"
  PROCESSING = "processing"
  IN_ROUTE = "in_route"
  DELIVERED = "delivered"
  RECEIVED = "received"

class Restaurant(models.Model):
  name = models.CharField(max_length=200)
  description = models.TextField(max_length=2000)
  owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="restaurants")
  is_blocked = models.BooleanField(default=False)
  is_active = models.BooleanField(default=True)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ["-created_at"]

  def __str__(self):
    return self.name

class Meal(models.Model):
  name = models.CharField(max_length=200)
  description = models.TextField(max_length=2000)
  price = models.DecimalField(max_digits=8, decimal_places=2)
  restaurant = models.ForeignKey('Restaurant', on_delete=models.PROTECT, related_name="meals")
  is_blocked = models.BooleanField(default=False)
  is_active = models.BooleanField(default=True)

  class Meta:
    ordering = ["name"]
    constraints = [
      CheckConstraint(condition=Q(price__gte=Decimal("0.01")), name="meal_price_positive"),
    ]

  def __str__(self):
    return f"{self.name} ({self.restaurant.name})"

class Order(models.Model):
  status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PLACED)
  restaurant = models.ForeignKey('Restaurant', on_delete=models.PROTECT, related_name="orders")
  customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
  coupon = models.ForeignKey('Coupon', on_delete=models.PROTECT, null=True, related_name="orders", blank=True)
  subtotal = models.DecimalField(max_digits=8, decimal_places=2)
  discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
  tip_amount = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
  total_amount = models.DecimalField(max_digits=8, decimal_places=2)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ["-created_at", "-id"]
    constraints = [
      CheckConstraint(condition=Q(tip_amount__gte=0), name="order_tip_non_negative"),
      CheckConstraint(condition=Q(subtotal__gte=0), name="order_subtotal_non_negative"),
      CheckConstraint(condition=Q(discount_amount__gte=0), name="order_discount_non_negative"),
    ]

  def __str__(self):
    return f"Order #{self.pk} - {self.status}"

class OrderItem(models.Model):
  order = models.ForeignKey('Order', on_delete=models.PROTECT, related_name="items")
  meal = models.ForeignKey('Meal', on_delete=models.PROTECT, related_name="order_items")
  quantity = models.PositiveIntegerField(default=1)
  unit_price = models.DecimalField(max_digits=8, decimal_places=2)

  class Meta:
    constraints = [
      CheckConstraint(condition=Q(quantity__gte=1), name="orderitem_quantity_min_1"),
      CheckConstraint(condition=Q(unit_price__gte=Decimal("0.01")), name="orderitem_unit_price_positive"),
      UniqueConstraint(fields=("order", "meal"), name="orderitem_unique_meal_per_order")
    ]

  def __str__(self):
    return f"{self.quantity} x {self.meal.name}"

class Coupon(models.Model):
  code = models.CharField(max_length=20, unique=True)
  discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
  is_active = models.BooleanField(default=True)
  expires_at = models.DateTimeField()

  class Meta:
    ordering = ["code"]
    constraints = [
      CheckConstraint(
        condition=Q(discount_percentage__gte=0) & Q(discount_percentage__lte=100),
        name="coupon_discount_0_to_100",
      ),
    ]

  def __str__(self):
    return f"{self.code} ({self.discount_percentage}%)"

class OrderStatusHistory(models.Model):
  order = models.ForeignKey('Order', on_delete=models.PROTECT, related_name="status_history")
  status = models.CharField(max_length=20, choices=OrderStatus.choices)
  changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="order_status_changes")
  changed_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ["changed_at"]

  def __str__(self):
    return f"Order #{self.order_id} -> {self.status}"
