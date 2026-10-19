
from rest_framework_simplejwt.tokens import AccessToken
from django.utils import timezone
from datetime import timedelta

from config.base_test import BaseAPITestCase, PASSWORD
from user.models import Role

LOGIN = "/api/auth/login/"
PROTECTED = "/api/restaurants/"

class RegisterTestCase(BaseAPITestCase):
  def test_customer_can_register(self):
    response = self.client.post("/api/auth/register/", {"email": "c1@test.com", "password": PASSWORD, "role": Role.CUSTOMER}, format="json")
    self.assertEqual(response.status_code, 201)
    self.assertIn("access_token", response.data["tokens"])
    self.assertNotIn("password", response.data["user"])

  def test_owner_can_register(self):
    response = self.client.post("/api/auth/register/", {"email": "o1@test.com", "password": PASSWORD, "role": Role.OWNER}, format="json")
    self.assertEqual(response.status_code, 201)
    self.assertIn("access_token", response.data["tokens"])
    self.assertNotIn("password", response.data["user"])

  def test_admin_cannot_register(self):
    response = self.client.post("/api/auth/register/", {"email": "a1@test.com", "password": PASSWORD, "role": Role.ADMIN}, format="json")
    self.assertEqual(response.status_code, 400)

  def test_empty_role_register(self):
    response = self.client.post("/api/auth/register/", {"email": "a1@test.com", "password": PASSWORD, "role": ""}, format="json")
    self.assertEqual(response.status_code, 400)

  def test_weak_password_register(self):
    response = self.client.post("/api/auth/register/", {"email": "c2@test.com", "password": "123", "role": Role.CUSTOMER}, format="json")
    self.assertEqual(response.status_code, 400)

  def test_missing_password_register(self):
    response = self.client.post("/api/auth/register/", {"email": "c2@test.com", "role": Role.CUSTOMER}, format="json")
    self.assertEqual(response.status_code, 400)

  def test_malformed_json_register(self):
    response = self.client.post("/api/auth/register/", "{not json", content_type="application/json")
    self.assertEqual(response.status_code, 400)

class LoginTestCase(BaseAPITestCase):
  def setUp(self):
    self.user = self.make_user("user@test.com")

  def post_login(self, email="user@test.com", password=PASSWORD):
    return self.client.post(LOGIN, {"email": email, "password": password}, format="json")

  def test_login_returns_tokens_and_the_token_works(self):
    response = self.post_login(self.user.email)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["user"]["email"],self.user.email)
    self.assertNotIn("password", response.data["user"])

    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access_token']}")
    self.assertEqual(self.client.get("/api/restaurants/").status_code, 200)

  def test_email_is_case_insensitive(self):
    self.assertEqual(self.post_login(self.user.email.upper()).status_code, 200)

  def test_wrong_password_and_unknown_email_give_the_same_error(self):
    wrong_password = self.post_login(password="Wrong!pass#92")
    unknown_email = self.post_login(email="nobody@test.com")

    for response in (wrong_password, unknown_email):
      self.assertEqual(response.status_code, 400)
      self.assertEqual(response.data["detail"], "Invalid email or password")

  def test_blocked_user_cannot_log_in(self):
    self.user.is_blocked = True
    self.user.save()

    response = self.post_login(self.user.email)

    self.assertEqual(response.status_code, 403)
    self.assertEqual(response.data["detail"], "User is blocked")

  def test_deleted_user_cannot_log_in(self):
    self.user.is_active = False
    self.user.save()

    response = self.post_login(self.user.email)

    self.assertEqual(response.status_code, 400)
    self.assertEqual(response.data["detail"], "Invalid email or password")

class TokenTestCase(BaseAPITestCase):
  def setUp(self):
    self.user = self.make_user("user@test.com")

  def get_with(self, token, scheme="Bearer"):
    self.client.credentials(HTTP_AUTHORIZATION=f"{scheme} {token}")
    return self.client.get(PROTECTED)

  def test_no_token_is_rejected(self):
    self.assertEqual(self.client.get(PROTECTED).status_code, 401)

  def test_garbage_token_is_rejected(self):
    self.assertEqual(self.get_with("not-a-token").status_code, 401)

  def test_tampered_token_is_rejected(self):
    token = self.login(self.user)
    tokens = list(token)
    tokens[-1] = "^xs"
    token = "".join(tokens)
    self.assertEqual(self.get_with(token).status_code, 401)

  def test_expired_token_is_rejected(self):
    token = AccessToken.for_user(self.user)
    token.set_exp(from_time=timezone.now() - timedelta(hours=2), lifetime=timedelta(minutes=30))

    self.assertEqual(self.get_with(str(token)).status_code, 401)

  def test_wrong_auth_scheme_is_rejected(self):
    self.assertEqual(self.get_with(self.login(self.user), scheme="Token").status_code, 401)

  def test_blocked_user_with_existing_token_is_rejected(self):
    token = self.login(self.user)
    self.assertEqual(self.get_with(token).status_code, 200)

    self.user.is_blocked = True
    self.user.save()

    self.assertEqual(self.get_with(token).status_code, 401)

  def test_unblocking_restores_access_for_same_token(self):
    token = self.login(self.user)
    self.user.is_blocked = True
    self.user.save()
    self.assertEqual(self.get_with(token).status_code, 401)

    self.user.is_blocked = False
    self.user.save()
    self.assertEqual(self.get_with(token).status_code, 200)
