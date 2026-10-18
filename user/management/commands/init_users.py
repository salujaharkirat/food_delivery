import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from user.models import Role, User



SEED_USERS = [
  {"email": "customer1@test.com", "role": Role.CUSTOMER},
  {"email": "customer2@test.com", "role": Role.CUSTOMER},
  {"email": "customer3@test.com", "role": Role.CUSTOMER},
  {"email": "customer4@test.com", "role": Role.CUSTOMER},
  {"email": "customer5@test.com", "role": Role.CUSTOMER},
  {"email": "admin1@test.com", "role": Role.ADMIN},
  {"email": "admin2@test.com", "role": Role.ADMIN},
]


class Command(BaseCommand):
  help = "Create the demo customers and admins (safe to run repeatedly; existing users are skipped)."

  def handle(self, *args, **options):
    password = os.environ.get("SEED_USER_PASSWORD") or ""

    try:
      validate_password(password)
    except ValidationError as exc:
      raise CommandError("Seed password is too weak: " + " ".join(exc.messages))

    created, skipped = 0, 0
    for entry in SEED_USERS:
      email = entry["email"]

      if User.objects.filter(email__iexact=email).exists():
        skipped += 1
        continue

      User.objects.create_user(email, password, role=entry["role"])
      created += 1

    self.stdout.write(self.style.SUCCESS(f"Users created: {created}, already existed: {skipped}"))
