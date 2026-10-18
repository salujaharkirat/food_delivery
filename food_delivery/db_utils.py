from .models import Restaurant

def get_visible_restaurants():
  return Restaurant.objects.filter(
    is_active=True,
    is_blocked=False,
    owner__is_active=True,
    owner__is_blocked=False
  )