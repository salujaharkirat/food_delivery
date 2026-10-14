from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from rest_framework.exceptions import ValidationError

from .models import Restaurant, Coupon, Meal, Order, OrderItem, OrderStatus, OrderStatusHistory


@transaction.atomic
def create_order(user, validated_data):
  restaurant_id = validated_data["restaurant_id"]
  order_items = validated_data["items"]
  coupon_code = validated_data.get("coupon_code")
  tip_amount = validated_data["tip_amount"]

  if not Restaurant.objects.filter(id=restaurant_id, is_active=True, is_blocked=False).exists():
    raise ValidationError({"message": "Restaurant does not exist."})

  meal_ids = [item["meal_id"] for item in order_items]
  if len(meal_ids) != len(set(meal_ids)):
    raise ValidationError({"message": "Each meal may appear only once; use quantity instead."})

  meals = {
    meal.pk: meal
    for meal in Meal.objects.filter(
      id__in=meal_ids, restaurant_id=restaurant_id, is_active=True, is_blocked=False
    )
  }

  missing_meals = set(meal_ids) - meals.keys()

  if missing_meals:
    raise ValidationError({"message": f"Meals not available at this restaurant {missing_meals}"})

  coupon = None
  if coupon_code:
    coupon = Coupon.objects.filter(
      code=coupon_code.strip(),
      is_active=True,
      expires_at__gt=timezone.now()
    ).first()

    if coupon is None:
      raise ValidationError({"message": f"Invalid or expired coupon code {coupon_code}"})
  

  subtotal = 0
  for item in order_items:
    subtotal += meals[item["meal_id"]].price * item["quantity"]

  discount_amount = 0
  if coupon:
    discount_amount = (subtotal * coupon.discount_percentage).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)


  order = Order.objects.create(
    restaurant_id=restaurant_id,
    customer=user,
    subtotal=subtotal,
    discount_amount=discount_amount,
    tip_amount=tip_amount,
    total_amount=subtotal - discount_amount + tip_amount
  )

  OrderStatusHistory.objects.create(
    order=order,
    status=OrderStatus.PLACED,
    changed_by=user
  )

  OrderItem.objects.bulk_create([
    OrderItem(
      order=order,
      meal=meals[item["meal_id"]],
      quantity=item["quantity"],
      unit_price=meals[item["meal_id"]].price
    )
    for item in order_items
  ])

  return order

    