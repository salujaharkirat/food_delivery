from config.base_test import BaseAPITestCase, PASSWORD

from user.models import Role, User

USERS = "/api/admin/users/"

def detail(user):
  return f"{USERS}{user.pk}/"
class AdminUserTests(BaseAPITestCase):
  def setUp(self):
    self.admin = self.make_admin()
    self.owner = self.make_owner()
    self.customer = self.make_user()
    self.auth_as(self.admin)

  def login_status(self, email, password=PASSWORD):
    self.client.credentials()
    return self.client.post("/api/auth/login/", {"email": email, "password": password}, format="json").status_code


  def test_all_users(self):
    response = self.client.get(USERS)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["count"], 3)
    self.assertEqual([user["id"] for user in response.data["results"]], sorted([self.admin.pk, self.customer.pk, self.owner.pk]))
    self.assertNotIn("password", response.data["results"][0])

  def test_include_blocked_and_deleted_users(self):
    self.customer.is_active = False
    self.owner.is_blocked = True
    self.customer.save()
    self.owner.save()

    response = self.client.get(USERS)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["count"], 3)

  def test_detail_user(self):
    response = self.client.get(detail(self.owner))

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["email"], self.owner.email)

  def test_unknown_user_is_not_found(self):
    url = f"{USERS}999999/"

    self.assertEqual(self.client.get(url).status_code, 404)
    self.assertEqual(self.client.patch(url, {"is_blocked": True}, format="json").status_code, 404)
    self.assertEqual(self.client.delete(url).status_code, 404)

  def test_create_customer(self):
    response = self.client.post(USERS, {"email": f"new-customer@test.com", "password": PASSWORD, "role": Role.CUSTOMER}, format="json")
    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data["user"]["role"], Role.CUSTOMER)

  def test_create_owner(self):
    response = self.client.post(USERS, {"email": f"new-owner@test.com", "password": PASSWORD, "role": Role.OWNER}, format="json")
    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data["user"]["role"], Role.OWNER)

  def test_create_user_ignores_privilege_flags(self):
    response = self.client.post(
      USERS,
      {
        "email": "attack@test.com",
        "password": PASSWORD,
        "role": Role.CUSTOMER,
        "is_builtin": True,
        "is_staff": True,
        "is_superuser": True
      }
    )

    self.assertEqual(response.status_code, 201)
    created = User.objects.get(email="attack@test.com")
    self.assertEqual((created.is_builtin, created.is_staff, created.is_superuser), (False, False, False))

  def test_patch_updates_email_and_role(self):
    response = self.client.patch(detail(self.customer), {"email": "Renamed@Test.com", "role": "owner"}, format="json")

    self.assertEqual(response.status_code, 200)
    self.customer.refresh_from_db()
    self.assertEqual((self.customer.email, self.customer.role), ("renamed@test.com", Role.OWNER))
    self.assertNotIn("password", response.data)

  def test_put_needs_email_and_role(self):
    full = {"email": "put@test.com", "role": "owner"}

    self.assertEqual(self.client.put(detail(self.customer), full, format="json").status_code, 200)
    self.assertEqual(self.client.put(detail(self.customer), {"role": "owner"}, format="json").status_code, 400)
    self.assertEqual(self.client.put(detail(self.customer), {"email": "put@test.com"}, format="json").status_code, 400)

  def test_update_rejects_admin_role_and_duplicate_email(self):
    self.assertEqual(self.client.patch(detail(self.customer), {"role": "admin"}, format="json").status_code, 400)
    self.assertEqual(self.client.patch(detail(self.customer), {"email": "OWNER@test.com"}, format="json").status_code, 400)
    self.assertEqual(self.client.patch(detail(self.customer), {"email": "customer@test.com"}, format="json").status_code, 200)

    self.customer.refresh_from_db()
    self.assertEqual(self.customer.role, Role.CUSTOMER)

  def test_put_needs_email_and_role(self):
    self.assertEqual(self.client.put(detail(self.customer), {"email": "put@test.com", "role": "owner"}, format="json").status_code, 200)
    self.assertEqual(self.client.put(detail(self.customer), {"role": "owner"}, format="json").status_code, 400)
    self.assertEqual(self.client.put(detail(self.customer), {"email": "put@test.com"}, format="json").status_code, 400)


  def test_update_ignores_privilege_flags(self):
    response = self.client.patch(
      detail(self.customer), {"is_builtin": True, "is_staff": True, "is_superuser": True}, format="json"
    )

    self.assertEqual(response.status_code, 200)
    self.customer.refresh_from_db()
    self.assertEqual((self.customer.is_builtin, self.customer.is_staff, self.customer.is_superuser), (False, False, False))

  def test_blocking_a_user_stops_login_and_tokens_and_unblocking_restores_them(self):
    token = self.login(self.customer)
    self.auth_as(self.admin)

    response = self.client.patch(detail(self.customer), {
      "is_blocked": True
    }, format="json")

    self.assertEqual(response.status_code, 200)

    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    self.assertEqual(self.client.get("/api/restaurants/").status_code, 401)

    self.auth_as(self.admin)

    response = self.client.patch(detail(self.customer), {
      "is_blocked": False
    }, format="json")

    self.assertEqual(response.status_code, 200)

    self.assertEqual(self.login_status("customer@test.com"), 200)
    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    self.assertEqual(self.client.get("/api/restaurants/").status_code, 200)

  def test_delete_is_a_soft_delete_and_stops_login(self):
    response = self.client.delete(detail(self.customer))

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["detail"], "User deleted successfully")
    self.assertTrue(User.objects.filter(pk=self.customer.pk).exists())
    self.customer.refresh_from_db()
    self.assertFalse(self.customer.is_active)

    self.assertEqual(self.login_status("customer@test.com"), 400)
    self.auth_as(self.admin)
    self.assertEqual(self.client.delete(detail(self.customer)).status_code, 404)

  def test_a_deleted_user_can_be_restored(self):
    self.client.delete(detail(self.customer))

    response = self.client.patch(detail(self.customer), {"is_active": True}, format="json")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(self.login_status("customer@test.com"), 200)


  def test_blocking_an_owner_hides_their_restaurants_from_customers(self):
    restaurant = self.make_restaurant(self.owner)
    url = f"/api/restaurants/{restaurant.pk}/"
    self.auth_as(self.customer)
    self.assertEqual(self.client.get(url).status_code, 200)

    self.auth_as(self.admin)
    self.client.patch(detail(self.owner), {"is_blocked": True}, format="json")

    self.auth_as(self.customer)
    self.assertEqual(self.client.get(url).status_code, 404)

    self.auth_as(self.admin)
    self.client.patch(detail(self.owner), {"is_blocked": False}, format="json")

    self.auth_as(self.customer)
    self.assertEqual(self.client.get(url).status_code, 200)

  def test_deleting_an_owner_hides_but_does_not_remove_their_data(self):
    restaurant = self.make_restaurant(self.owner)
    meal = self.make_meal(restaurant)

    self.assertEqual(self.client.delete(detail(self.owner)).status_code, 200)

    restaurant.refresh_from_db()
    meal.refresh_from_db()
    self.assertTrue(restaurant.is_active)
    self.assertTrue(meal.is_active)

    self.auth_as(self.customer)
    self.assertEqual(self.client.get(f"/api/restaurants/{restaurant.pk}/").status_code, 404)
    self.assertEqual(self.client.get(f"/api/restaurants/{restaurant.pk}/meals/{meal.pk}/").status_code, 404)

  def test_builtin_admin_cannot_be_changed_blocked_or_deleted(self):
    url = detail(self.admin)

    for body in ({"is_blocked": True}, {"is_active": False}):
      with self.subTest(patch=body):
        self.assertEqual(self.client.patch(url, body, format="json").status_code, 403)

    self.assertEqual(self.client.put(url, {"email": "x@test.com", "role": "owner"}, format="json").status_code, 403)
    self.assertEqual(self.client.delete(url).status_code, 403)

    self.admin.refresh_from_db()
    self.assertEqual(self.admin.email, "admin@test.com")
    self.assertEqual(self.admin.role, Role.ADMIN)
    self.assertTrue(self.admin.is_active)
    self.assertFalse(self.admin.is_blocked)

  def test_builtin_admin_role_cannot_be_changed(self):
    self.assertEqual(self.client.patch(detail(self.admin), {"role": "admin"}, format="json").status_code, 400)
    self.assertEqual(self.client.patch(detail(self.admin), {"role": "customer"}, format="json").status_code, 403)

    self.admin.refresh_from_db()
    self.assertEqual(self.admin.role, Role.ADMIN)
