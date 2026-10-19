from decimal import Decimal
from config.base_test import BaseAPITestCase, PASSWORD

from user.models import Role, User
from food_delivery.models import Restaurant, Meal

USERS = "/api/admin/users/"
RESTAURANTS = "/api/admin/restaurants/"
MEALS = "/api/admin/meals/"

def detail(user):
  return f"{USERS}{user.pk}/"

def ids(response):
  return {item["id"] for item in response.data["results"]}
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

class AdminRestaurantTests(BaseAPITestCase):
  def setUp(self):
    self.admin = self.make_admin()
    self.owner = self.make_owner()
    self.customer = self.make_user()
    self.other_owner = self.make_owner(email="other-owner@test.com")
    self.restaurant = self.make_restaurant(self.owner)
    self.meal = self.make_meal(self.restaurant)
    self.url = f"{RESTAURANTS}{self.restaurant.pk}/"
    self.public_url = f"/api/restaurants/{self.restaurant.pk}/"
    self.auth_as(self.admin)

  def test_list_includes_blocked_and_deleted_restaurants(self):
    blocked = self.make_restaurant(self.owner, name="Blocked", is_blocked=True)
    deleted = self.make_restaurant(self.owner, name="Deleted", is_active=False)

    response = self.client.get(RESTAURANTS)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(ids(response), {self.restaurant.pk, blocked.pk, deleted.pk})

  def test_deleted_restaurant_can_be_read(self):
    self.restaurant.is_active = False
    self.restaurant.save()

    response = self.client.get(self.url)

    self.assertEqual(response.status_code, 200)
    self.assertFalse(response.data["is_active"])

  def test_unknown_restaurant_is_not_found(self):
    url = f"{RESTAURANTS}999999/"

    self.assertEqual(self.client.get(url).status_code, 404)
    self.assertEqual(self.client.patch(url, {"name": "x"}, format="json").status_code, 404)
    self.assertEqual(self.client.delete(url).status_code, 404)

  def test_create_assigns_the_given_owner(self):
    response = self.client.post(
      RESTAURANTS, {"name": "New", "description": "d", "owner": self.other_owner.pk}, format="json"
    )

    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data["owner"], self.other_owner.pk)
    self.assertEqual(response.data["owner_email"], self.other_owner.email)
    self.assertEqual(Restaurant.objects.get(pk=response.data["id"]).owner, self.other_owner)

  def test_create_ignores_blocked_and_active_flags(self):
    response = self.client.post(
      RESTAURANTS,
      {"name": "New", "description": "d", "owner": self.owner.pk, "is_blocked": True, "is_active": False},
      format="json",
    )

    created = Restaurant.objects.get(pk=response.data["id"])
    self.assertFalse(created.is_blocked)
    self.assertTrue(created.is_active)

  def test_create_needs_an_active_owner(self):
    blocked_owner = self.make_owner("blocked@test.com", is_blocked=True)
    deleted_owner = self.make_owner("deleted@test.com", is_active=False)


    self.assertEqual(self.client.post(RESTAURANTS,{"name": "New", "description": "d", "owner": blocked_owner.pk}).status_code, 400)
    self.assertEqual(self.client.post(RESTAURANTS,{"name": "New", "description": "d", "owner": deleted_owner.pk}).status_code, 400)

  def test_put_and_patch_update_the_restaurant(self):
    put = self.client.put(
      self.url, {"name": "Put", "description": "Put desc", "owner": self.owner.pk}, format="json"
    )
    self.assertEqual(put.status_code, 200)

    patch = self.client.patch(self.url, {"name": "Patched"}, format="json")
    self.assertEqual(patch.status_code, 200)

    self.restaurant.refresh_from_db()
    self.assertEqual((self.restaurant.name, self.restaurant.description), ("Patched", "Put desc"))
    self.assertEqual(self.restaurant.owner, self.owner)

  def test_cannot_move_a_restaurant_to_an_invalid_owner(self):
    self.assertEqual(self.client.patch(self.url, {"owner": self.customer.pk}, format="json").status_code, 400)
    self.assertEqual(self.client.patch(self.url, {"owner": 999999}, format="json").status_code, 400)

    self.restaurant.refresh_from_db()
    self.assertEqual(self.restaurant.owner, self.owner)

  def test_admin_can_still_edit_a_restaurant_whose_owner_is_blocked(self):
    self.owner.is_blocked = True
    self.owner.save()

    self.assertEqual(self.client.patch(self.url, {"name": "Fixed by admin"}, format="json").status_code, 200)

  def test_blocking_hides_the_restaurant_and_its_meals_from_customers(self):
    self.assertEqual(self.client.patch(self.url, {"is_blocked": True}, format="json").status_code, 200)

    self.auth_as(self.customer)
    self.assertNotIn(self.restaurant.pk, ids(self.client.get("/api/restaurants/")))
    self.assertEqual(self.client.get(self.public_url).status_code, 404)
    self.assertEqual(self.client.get(f"{self.public_url}meals/").status_code, 404)
    self.assertEqual(self.client.get(f"{self.public_url}meals/{self.meal.pk}/").status_code, 404)

  def test_owner_still_sees_a_blocked_restaurant_but_cannot_change_it(self):
    self.client.patch(self.url, {"is_blocked": True}, format="json")

    self.auth_as(self.owner)
    self.assertIn(self.restaurant.pk, ids(self.client.get("/api/restaurants/")))
    self.assertTrue(self.client.get(self.public_url).data["is_blocked"])
    self.assertEqual(self.client.patch(self.public_url, {"is_blocked": False}, format="json").status_code, 403)

    self.restaurant.refresh_from_db()
    self.assertTrue(self.restaurant.is_blocked)

  def test_customers_cannot_order_from_a_blocked_restaurant(self):
    self.client.patch(self.url, {"is_blocked": True}, format="json")
    order = {"restaurant_id": self.restaurant.pk, "items": [{"meal_id": self.meal.pk, "quantity": 1}]}

    self.auth_as(self.customer)

    self.assertEqual(self.client.post("/api/orders/", order).status_code, 400)


class AdminMealTests(BaseAPITestCase):
  def setUp(self):
    self.admin = self.make_admin()
    self.owner = self.make_owner()
    self.other_owner = self.make_owner("other-owner@test.com")
    self.customer = self.make_user()
    self.restaurant = self.make_restaurant(self.owner)
    self.meal = self.make_meal(self.restaurant)
    self.url = f"{MEALS}{self.meal.pk}/"
    self.public_list = f"/api/restaurants/{self.restaurant.pk}/meals/"
    self.public_url = f"{self.public_list}{self.meal.pk}/"
    self.auth_as(self.admin)

  def test_list_includes_blocked_and_deleted_meals(self):
    blocked = self.make_meal(self.restaurant, name="Blocked", is_blocked=True)
    deleted = self.make_meal(self.restaurant, name="Deleted", is_active=False)

    response = self.client.get(MEALS)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(ids(response), {self.meal.pk, blocked.pk, deleted.pk})

  def test_output_shows_restaurant(self):
    row = self.client.get(self.url).data

    self.assertEqual(row["restaurant"], self.restaurant.pk)
    self.assertEqual(row["restaurant_name"], self.restaurant.name)
    self.assertEqual(row["price"], "10.00")

  def test_deleted_meal_can_still_be_read(self):
    self.meal.is_active = False
    self.meal.save()

    self.assertEqual(self.client.get(self.url).status_code, 200)

  def test_unknown_meal_is_not_found(self):
    url = f"{MEALS}999999/"

    self.assertEqual(self.client.get(url).status_code, 404)
    self.assertEqual(self.client.patch(url, {"name": "x"}, format="json").status_code, 404)
    self.assertEqual(self.client.delete(url).status_code, 404)

  def test_create_a_meal_for_any_restaurant(self):
    second = self.make_restaurant(self.other_owner, name="Second")

    response = self.client.post(
      MEALS, {"name": "Pasta", "description": "d", "price": "12.50", "restaurant": second.pk}, format="json"
    )

    self.assertEqual(response.status_code, 201)
    created = Meal.objects.get(pk=response.data["id"])
    self.assertEqual((created.restaurant, created.price), (second, Decimal("12.50")))
    self.assertTrue(created.is_active)
    self.assertFalse(created.is_blocked)

  def test_create_rejects_inactive_blocked_restaurants(self):
    blocked = self.make_restaurant(self.owner, name="Blocked", is_blocked=True)
    deleted = self.make_restaurant(self.owner, name="Deleted", is_active=False)

    self.assertEqual(self.client.post(MEALS, {
      "name": "Pasta",
      "description": "d",
      "price": "5.00",
      "restaurant": blocked.pk
    }).status_code, 400)

    self.assertEqual(self.client.post(MEALS, {
      "name": "Pasta",
      "description": "d",
      "price": "5.00",
      "restaurant": deleted.pk
    }).status_code, 400)

  def test_put_and_patch_update_the_meal(self):
    put = self.client.put(
      self.url, {"name": "Put", "description": "d", "price": "5.00", "restaurant": self.restaurant.pk}, format="json"
    )
    self.assertEqual(put.status_code, 200)

    patch = self.client.patch(self.url, {"price": "6.00"}, format="json")
    self.assertEqual(patch.status_code, 200)

    self.meal.refresh_from_db()
    self.assertEqual((self.meal.name, self.meal.price), ("Put", Decimal("6.00")))

  def test_meal_can_move_only_to_an_available_restaurant(self):
    second = self.make_restaurant(self.other_owner, name="Second")
    blocked = self.make_restaurant(self.owner, name="Blocked", is_blocked=True)

    self.assertEqual(self.client.patch(self.url, {"restaurant": second.pk}, format="json").status_code, 200)
    self.meal.refresh_from_db()
    self.assertEqual(self.meal.restaurant, second)

    self.assertEqual(self.client.patch(self.url, {"restaurant": blocked.pk}, format="json").status_code, 400)
    self.assertEqual(self.client.patch(self.url, {"restaurant": 999999}, format="json").status_code, 400)
    self.assertEqual(self.meal.restaurant, second)

  def test_admin_can_still_edit_a_meal_of_a_blocked_restaurant(self):
    self.restaurant.is_blocked = True
    self.restaurant.save()

    self.assertEqual(self.client.patch(self.url, {"price": "7.00"}, format="json").status_code, 200)

  def test_blocking_hides_the_meal_from_customers_and_ordering(self):
    self.assertEqual(self.client.patch(self.url, {"is_blocked": True}, format="json").status_code, 200)

    self.auth_as(self.customer)
    self.assertNotIn(self.meal.pk, ids(self.client.get(self.public_list)))
    self.assertEqual(self.client.get(self.public_url).status_code, 404)

    order = {"restaurant_id": self.restaurant.pk, "items": [{"meal_id": self.meal.pk, "quantity": 1}]}
    self.assertEqual(self.client.post("/api/orders/", order, format="json").status_code, 400)

  def test_unblocking_makes_the_meal_visible_again(self):
    self.client.patch(self.url, {"is_blocked": True}, format="json")
    self.client.patch(self.url, {"is_blocked": False}, format="json")

    self.auth_as(self.customer)

    self.assertEqual(self.client.get(self.public_url).status_code, 200)

  def test_owner_still_sees_a_blocked_meal_but_cannot_change_it(self):
    self.client.patch(self.url, {"is_blocked": True}, format="json")

    self.auth_as(self.owner)
    self.assertIn(self.meal.pk, ids(self.client.get(self.public_list)))
    self.assertEqual(self.client.patch(self.public_url, {"is_blocked": False}, format="json").status_code, 403)
    self.assertEqual(self.client.delete(self.public_url).status_code, 403)

    self.meal.refresh_from_db()
    self.assertTrue(self.meal.is_blocked)

  def test_delete_is_a_soft_delete(self):
    response = self.client.delete(self.url)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["detail"], "Meal deleted successfully")
    self.meal.refresh_from_db()
    self.assertFalse(self.meal.is_active)

    self.auth_as(self.customer)
    self.assertEqual(self.client.get(self.public_url).status_code, 404)
    self.auth_as(self.owner)
    self.assertEqual(self.client.get(self.public_url).status_code, 404)
    self.auth_as(self.admin)
    self.assertEqual(self.client.delete(self.url).status_code, 404)

  def test_changing_the_price_does_not_touch_old_orders(self):
    order = self.make_order(self.customer, self.restaurant, [(self.meal, 2)])

    self.client.patch(self.url, {"price": "99.00"}, format="json")

    self.auth_as(self.customer)
    detail = self.client.get(f"/api/orders/{order.pk}/").data
    self.assertEqual(detail["items"][0]["unit_price"], "10.00")
    self.assertEqual(detail["subtotal"], "20.00")
