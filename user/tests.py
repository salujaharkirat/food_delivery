from config.base_test import BaseAPITestCase, PASSWORD

from user.models import Role

LOGIN = "/api/auth/login/"

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

  def test_malformed_json_register(self):
    response = self.client.post("/api/auth/register/", {"email": "c2@test.com", "role": Role.CUSTOMER}, format="json")
    self.assertEqual(response.status_code, 400)

class LoginTestCase(BaseAPITestCase):
  def setUp(self):
    self.user = self.make_user("c1@test.com")

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
