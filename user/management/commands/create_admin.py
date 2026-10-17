import os

from django.contrib.auth.password_validation import validate_password
from user.models import Role, User
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError


class Command(BaseCommand):
  def handle(self, *args, **options):
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or ""

    if not email or not password:
      raise CommandError("Please pass correct email and password")

    if User.objects.filter(email__iexact=email).exists():
      raise CommandError(f"A user exits with the same {email}")

    try:
      validate_password(password)
    except ValidationError:
      raise CommandError(f"Password does not meet the guidelines")

    User.objects.create_superuser(email=email, password=password, is_builtin=True)
    self.stdout.write(f"Built in admin created {email}")
    return

    