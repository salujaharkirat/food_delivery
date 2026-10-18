from collections import Counter
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from user.models import Role, User
from food_delivery.db_utils import get_visible_restaurants
from food_delivery.models import Coupon, Order, OrderStatus
from food_delivery.service import change_order_status, create_order

# One entry per order. "items" are (meal name, quantity). "steps" are the status changes applied after the
# order is placed, as (who, new status): "owner" is the restaurant's owner, "customer" is the order's customer.
SEED_ORDERS = [
  {
    "customer": "customer1@test.com",
    "restaurant": "Bombay Brasserie",
    "items": [("Butter Chicken", 2), ("Garlic Naan", 2)],
    "tip": "3.00",
    "coupon": None,
    "steps": [
      ("owner", OrderStatus.PROCESSING),
      ("owner", OrderStatus.IN_ROUTE),
      ("owner", OrderStatus.DELIVERED),
      ("customer", OrderStatus.RECEIVED),
    ],
  },
  {
    "customer": "customer1@test.com",
    "restaurant": "Mama Rosa's Trattoria",
    "items": [("Margherita Pizza", 1), ("Tiramisu", 1)],
    "tip": "1.50",
    "coupon": "SAVE15",
    "steps": [
      ("owner", OrderStatus.PROCESSING),
      ("owner", OrderStatus.IN_ROUTE),
      ("owner", OrderStatus.DELIVERED),
    ],
  },
  {
    "customer": "customer2@test.com",
    "restaurant": "Sakura Sushi & Ramen House",
    "items": [("Tonkotsu Ramen", 2), ("Miso Soup", 1)],
    "tip": "2.00",
    "coupon": None,
    "steps": [
      ("owner", OrderStatus.PROCESSING),
      ("owner", OrderStatus.IN_ROUTE),
    ],
  },
  {
    "customer": "customer2@test.com",
    "restaurant": "El Camino Taqueria",
    "items": [("Carne Asada Tacos (3 pcs)", 1), ("Churros", 2)],
    "tip": "0.00",
    "coupon": None,
    "steps": [
      ("owner", OrderStatus.PROCESSING),
    ],
  },
  {
    "customer": "customer3@test.com",
    "restaurant": "Bombay Brasserie",
    "items": [("Chicken Biryani", 1), ("Mango Lassi", 2)],
    "tip": "1.00",
    "coupon": None,
    "steps": [],
  },
  {
    "customer": "customer3@test.com",
    "restaurant": "Bangkok Garden",
    "items": [("Pad Thai", 1), ("Green Curry", 1)],
    "tip": "2.00",
    "coupon": None,
    "steps": [
      ("customer", OrderStatus.CANCELED),
    ],
  },
  {
    "customer": "customer4@test.com",
    "restaurant": "Fresh & Co. Salad Kitchen",
    "items": [("Quinoa Power Bowl", 2)],
    "tip": "0.00",
    "coupon": None,
    "steps": [
      ("owner", OrderStatus.PROCESSING),
      ("owner", OrderStatus.CANCELED),
    ],
  },
  {
    "customer": "customer4@test.com",
    "restaurant": "Bombay Brasserie",
    "items": [("Lamb Rogan Josh", 1), ("Garlic Naan", 1)],
    "tip": "2.50",
    "coupon": None,
    "steps": [],
  },
  {
    "customer": "customer5@test.com",
    "restaurant": "Mama Rosa's Trattoria",
    "items": [("Pepperoni Pizza", 2), ("Lasagna al Forno", 1)],
    "tip": "4.00",
    "coupon": "WELCOME10",
    "steps": [
      ("owner", OrderStatus.PROCESSING),
      ("owner", OrderStatus.IN_ROUTE),
      ("owner", OrderStatus.DELIVERED),
      ("customer", OrderStatus.RECEIVED),
    ],
  },
  {
    "customer": "customer5@test.com",
    "restaurant": "Sakura Sushi & Ramen House",
    "items": [("California Roll", 2), ("Salmon Nigiri (2 pcs)", 2)],
    "tip": "1.50",
    "coupon": None,
    "steps": [],
  },
]


class Command(BaseCommand):
  help = (
    "Create demo orders in every status. Run init_users, init_restaurants_and_meals and init_coupons first. "
    "Skipped if any order already exists."
  )

  def handle(self, *args, **options):
    if Order.objects.exists():
      self.stdout.write("Orders already exist, nothing to do.")
      return

    plans = self.resolve(SEED_ORDERS)

    counts = Counter()
    with transaction.atomic():
      for plan in plans:
        order = create_order(plan["customer"], plan["data"])

        for who, new_status in plan["steps"]:
          actor = plan["owner"] if who == "owner" else plan["customer"]
          order = change_order_status(actor, order.pk, new_status)

        counts[order.status] += 1

    summary = ", ".join(f"{status}: {number}" for status, number in counts.items())
    self.stdout.write(self.style.SUCCESS(f"Orders created: {sum(counts.values())} ({summary})"))

  def resolve(self, specs):
    # Look everything up before writing anything, so a missing seed fails early with a clear message.
    problems, plans = [], []

    for spec in specs:
      customer = User.objects.filter(email__iexact=spec["customer"], role=Role.CUSTOMER).first()
      restaurant = get_visible_restaurants().filter(name=spec["restaurant"]).first()

      if customer is None or restaurant is None:
        continue

      if spec["coupon"] and not Coupon.objects.filter(code=spec["coupon"]).exists():
        problems.append(f"coupon {spec['coupon']} (run init_coupons)")

      items = []
      for meal_name, quantity in spec["items"]:
        meal = restaurant.meals.filter(name=meal_name, is_active=True, is_blocked=False).first()
        if meal is None:
          problems.append(f"meal '{meal_name}' at '{restaurant.name}' (run init_restaurants_and_meals)")
          continue
        items.append({"meal_id": meal.pk, "quantity": quantity})

      data = {"restaurant_id": restaurant.pk, "items": items, "tip_amount": Decimal(spec["tip"])}
      if spec["coupon"]:
        data["coupon_code"] = spec["coupon"]

      plans.append({"customer": customer, "owner": restaurant.owner, "data": data, "steps": spec["steps"]})

    if problems:
      raise CommandError("Missing data: " + "; ".join(sorted(set(problems))))

    return plans
