import os

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from user.models import User

REQUIRED_ENV = ["ADMIN_EMAIL", "ADMIN_PASSWORD", "SEED_USER_PASSWORD"]


class Command(BaseCommand):
  help = "Seed a fresh database: built-in admin, users, restaurants and meals, coupons, orders (safe to run repeatedly)."

  def handle(self, *args, **options):
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
      raise CommandError("Set these variables in .env first: " + ", ".join(missing))

    steps = [
      ("Built-in admin", "create_admin"),
      ("Users", "init_users"),
      ("Restaurants and meals", "init_restaurants_and_meals"),
      ("Coupons", "init_coupons"),
      ("Orders", "init_orders"),
    ]

    for title, command in steps:
      self.stdout.write(self.style.MIGRATE_HEADING(f"{title} ({command})"))

      # create_admin refuses to run twice, so skip it when the built-in admin is already there.
      if command == "create_admin" and User.objects.filter(is_builtin=True).exists():
        self.stdout.write("  Built-in admin already exists, skipping.")
        continue

      call_command(command, stdout=self.stdout, stderr=self.stderr)

    self.stdout.write(self.style.SUCCESS("Database seeded."))
