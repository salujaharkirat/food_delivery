import random

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP


from food_delivery.models import Coupon

COUPONS = [
  ("WELCOME10", 10),
  ("SAVE15", 15),
  ("SAVE20", 20),
  ("SAVE50", 50),
]


class Command(BaseCommand):
  help = "Create or refresh the demo coupons (safe to run repeatedly)."

  def handle(self, *args, **kwargs):
    expires_at = timezone.now() + timedelta(days=365)

    for code, percent in COUPONS:
      Coupon.objects.update_or_create(
        code=code,
        defaults={
          "discount_percentage": Decimal(percent),
          "is_active": True,
          "expires_at": expires_at
        }
      )

    self.stdout.write(f"SUCCESS {len(COUPONS)} created")
