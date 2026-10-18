import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from user.models import Role, User
from food_delivery.models import Meal, Restaurant

# Each restaurant belongs to an owner account (created if missing, with SEED_USER_PASSWORD).
# A meal is (name, description, price).
SEED_RESTAURANTS = [
  {
    "owner": "owner1@test.com",
    "name": "Bombay Brasserie",
    "description": "Indian: North Indian curries, tandoori grills and freshly baked naan",
    "meals": [
      ("Butter Chicken", "Tandoori chicken in a creamy tomato and fenugreek sauce", "13.50"),
      ("Paneer Tikka Masala", "Char-grilled paneer in a spiced onion and tomato gravy", "12.50"),
      ("Lamb Rogan Josh", "Slow-cooked Kashmiri lamb curry", "15.00"),
      ("Chicken Biryani", "Fragrant basmati rice layered with spiced chicken", "13.00"),
      ("Garlic Naan", "Oven-baked flatbread brushed with garlic butter", "3.00"),
      ("Mango Lassi", "Chilled yoghurt and Alphonso mango drink", "4.00"),
    ],
  },
  {
    "owner": "owner1@test.com",
    "name": "Mama Rosa's Trattoria",
    "description": "Italian: wood-fired pizza, fresh pasta and classic desserts",
    "meals": [
      ("Margherita Pizza", "San Marzano tomato, mozzarella and fresh basil", "11.50"),
      ("Pepperoni Pizza", "Spicy pepperoni with mozzarella", "13.00"),
      ("Spaghetti Carbonara", "Egg, pecorino, guanciale and black pepper", "12.50"),
      ("Lasagna al Forno", "Beef ragu, bechamel and parmesan, oven baked", "14.00"),
      ("Tiramisu", "Mascarpone, espresso and cocoa", "6.50"),
    ],
  },
  {
    "owner": "owner2@test.com",
    "name": "Sakura Sushi & Ramen House",
    "description": "Japanese: sushi, ramen and bento boxes",
    "meals": [
      ("Salmon Nigiri (2 pcs)", "Fresh salmon on seasoned rice", "6.00"),
      ("California Roll", "Crab, avocado and cucumber", "8.50"),
      ("Tonkotsu Ramen", "Pork broth, noodles, soft egg and chashu", "13.50"),
      ("Chicken Katsu Bento", "Crispy chicken cutlet with rice and salad", "12.00"),
      ("Miso Soup", "Tofu, seaweed and spring onion", "3.50"),
    ],
  },
  {
    "owner": "owner2@test.com",
    "name": "El Camino Taqueria",
    "description": "Mexican: street-style tacos, burritos and nachos",
    "meals": [
      ("Carne Asada Tacos (3 pcs)", "Grilled steak, salsa verde and lime", "9.50"),
      ("Chicken Burrito", "Grilled chicken, rice, black beans and cheese", "10.50"),
      ("Loaded Nachos", "Cheese, jalapenos, pico de gallo and sour cream", "8.50"),
      ("Guacamole and Chips", "Fresh avocado with crispy tortilla chips", "6.00"),
      ("Churros", "Cinnamon sugar with a chocolate dipping sauce", "5.50"),
    ],
  },
  {
    "owner": "owner3@test.com",
    "name": "Bangkok Garden",
    "description": "Thai: noodles, curries and soups",
    "meals": [
      ("Pad Thai", "Rice noodles, prawns, peanuts and lime", "12.50"),
      ("Green Curry", "Chicken in a spicy coconut green curry", "13.00"),
      ("Tom Yum Soup", "Hot and sour soup with prawns", "8.50"),
      ("Mango Sticky Rice", "Sweet coconut sticky rice with fresh mango", "6.50"),
    ],
  },
  {
    "owner": "owner3@test.com",
    "name": "Fresh & Co. Salad Kitchen",
    "description": "Healthy: salads, grain bowls and smoothies",
    "meals": [
      ("Quinoa Power Bowl", "Quinoa, roasted vegetables, chickpeas and tahini", "11.00"),
      ("Chicken Caesar Salad", "Romaine, parmesan, croutons and grilled chicken", "9.50"),
      ("Avocado Toast", "Sourdough, smashed avocado and a poached egg", "8.00"),
      ("Berry Smoothie", "Mixed berries, banana and almond milk", "6.00"),
    ],
  },
]


class Command(BaseCommand):
  help = "Create demo owners, restaurants and meals (safe to run repeatedly; existing records are skipped)."

  def handle(self, *args, **options):
    password = os.environ.get("SEED_USER_PASSWORD") or ""

    try:
      validate_password(password)
    except ValidationError as exc:
      raise CommandError("Seed password is too weak or missing (SEED_USER_PASSWORD): " + " ".join(exc.messages))

    owners_created, restaurants_created, meals_created = 0, 0, 0

    with transaction.atomic():
      for entry in SEED_RESTAURANTS:
        owner = User.objects.filter(email__iexact=entry["owner"]).first()

        if owner is None:
          owner = User.objects.create_user(entry["owner"], password, role=Role.OWNER)
          owners_created += 1
        elif owner.role != Role.OWNER:
          raise CommandError(f"{entry['owner']} already exists but is not an owner.")

        restaurant, created = Restaurant.objects.get_or_create(
          owner=owner, name=entry["name"], defaults={"description": entry["description"]}
        )
        restaurants_created += int(created)

        for name, description, price in entry["meals"]:
          _, created = Meal.objects.get_or_create(
            restaurant=restaurant, name=name, defaults={"description": description, "price": price}
          )
          meals_created += int(created)

    self.stdout.write(self.style.SUCCESS(
      f"Owners created: {owners_created}, restaurants created: {restaurants_created}, meals created: {meals_created}"
    ))
