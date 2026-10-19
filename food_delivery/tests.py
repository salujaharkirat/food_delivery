from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from user.models import User, Role
from food_delivery.models import Restaurant, Order, Meal

from config.base_test import BaseAPITestCase

RESTAURANTS = "/api/restaurants/"

def ids(response):
  return {item["id"] for item in response.data["results"]}

class OwnerRestaurantTests(BaseAPITestCase):
  def setUp(self):
    self.owner = self.make_owner()
    self.other_owner = self.make_owner("other@test.com")
    self.restaurant = self.make_restaurant(self.owner)
    self.others_restaurant = self.make_restaurant(self.other_owner, name="Not Mine")
    self.url = f"{RESTAURANTS}{self.restaurant.pk}/"
    self.auth_as(self.owner)

  def test_create_restaurant_uses_the_token_owner(self):
    response = self.client.post(
       RESTAURANTS, {"name": "New Place", "description": "d", "owner": self.owner.pk}, format="json"
    )

    self.assertEqual(response.status_code, 201)
    created = Restaurant.objects.get(pk=response.data["id"])
    self.assertEqual(created.owner, self.owner)

  def test_create_ignores_blocked_and_active_flags(self):
    response = self.client.post(
      RESTAURANTS, {"name": "New", "description": "d", "is_blocked": True, "is_active": False}, format="json"
    )

    created = Restaurant.objects.get(pk=response.data["id"])
    self.assertFalse(created.is_blocked)
    self.assertTrue(created.is_active)

  def test_list_shows_own_active_restaurants_including_blocked(self):
    blocked = self.make_restaurant(self.owner, name="Blocked", is_blocked=True)
    deleted = self.make_restaurant(self.owner, name="Deleted", is_active=False)

    listed = ids(self.client.get(RESTAURANTS))

    self.assertEqual(listed, {self.restaurant.pk, blocked.pk})
    self.assertNotIn(deleted.pk, listed)
    self.assertNotIn(self.others_restaurant.pk, listed)

  def test_put_and_patch_update_the_restaurant(self):
    put = self.client.put(self.url, {"name": "Put Name", "description": "Put desc"}, format="json")
    self.assertEqual(put.status_code, 200)
    self.restaurant.refresh_from_db()
    self.assertEqual((self.restaurant.name, self.restaurant.description), ("Put Name", "Put desc"))

    patch = self.client.patch(self.url, {"name": "Patched"}, format="json")
    self.assertEqual(patch.status_code, 200)
    self.restaurant.refresh_from_db()
    self.assertEqual((self.restaurant.name, self.restaurant.description), ("Patched", "Put desc"))

  def test_delete_is_a_soft_delete(self):
    response = self.client.delete(self.url)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["detail"], "Restaurant deleted successfully")

    self.restaurant.refresh_from_db()
    self.assertFalse(self.restaurant.is_active)

    self.assertEqual(self.client.get(self.url).status_code, 404)
    self.assertNotIn(self.restaurant.pk, ids(self.client.get(RESTAURANTS)))
    self.assertEqual(self.client.delete(self.url).status_code, 404)

  def test_another_owners_restaurant_is_not_found(self):
    url = f"{RESTAURANTS}{self.others_restaurant.pk}/"
    body = {"name": "Hijacked", "description": "d"}

    self.assertEqual(self.client.get(url).status_code, 404)
    self.assertEqual(self.client.put(url, body, format="json").status_code, 404)
    self.assertEqual(self.client.patch(url, body, format="json").status_code, 404)
    self.assertEqual(self.client.delete(url).status_code, 404)

    self.others_restaurant.refresh_from_db()
    self.assertEqual(self.others_restaurant.name, "Not Mine")
    self.assertTrue(self.others_restaurant.is_active)

  def test_blocked_restaurant_is_visible_but_cannot_be_changed(self):
    original_name = self.restaurant.name
    self.restaurant.is_blocked = True
    self.restaurant.save()
    body = {"name": "Changed", "description": "d"}

    detail = self.client.get(self.url)
    self.assertEqual(detail.status_code, 200)
    self.assertTrue(detail.data["is_blocked"])

    self.assertEqual(self.client.put(self.url, body, format="json").status_code, 403)
    self.assertEqual(self.client.patch(self.url, body, format="json").status_code, 403)
    self.assertEqual(self.client.delete(self.url).status_code, 403)

    self.restaurant.refresh_from_db()
    self.assertEqual(self.restaurant.name, original_name)
    self.assertTrue(self.restaurant.is_active)

  def test_owner_cannot_unblock_a_restaurant(self):
    self.restaurant.is_blocked = True
    self.restaurant.save()

    response = self.client.patch(self.url, {"is_blocked": False}, format="json")

    self.assertEqual(response.status_code, 403)
    self.restaurant.refresh_from_db()
    self.assertTrue(self.restaurant.is_blocked)

  def test_update_ignores_protected_fields(self):
    response = self.client.patch(
      self.url,
      {"name": "Renamed", "is_blocked": True, "is_active": False, "owner": self.other_owner.pk},
      format="json",
    )

    self.assertEqual(response.status_code, 200)
    self.restaurant.refresh_from_db()
    self.assertEqual(self.restaurant.name, "Renamed")
    self.assertEqual(self.restaurant.owner, self.owner)
    self.assertTrue(self.restaurant.is_active)
    self.assertFalse(self.restaurant.is_blocked)

  def test_invalid_input_is_rejected(self):
    self.assertEqual(self.client.post(RESTAURANTS, {"name": "", "description": "d"}, format="json").status_code, 400)
    self.assertEqual(self.client.put(self.url, {"description": "d"}, format="json").status_code, 400)

class OwnerMealTests(BaseAPITestCase):
  def setUp(self):
    self.owner = self.make_owner()
    self.other_owner = self.make_owner("other@test.com")
    self.restaurant = self.make_restaurant(self.owner)
    self.others_restaurant = self.make_restaurant(self.other_owner, name="Not Mine")
    self.meal = self.make_meal(self.restaurant)
    self.others_meal = self.make_meal(self.others_restaurant, name="Not My Meal")
    self.list_url = f"{RESTAURANTS}{self.restaurant.pk}/meals/"
    self.url = f"{self.list_url}{self.meal.pk}/"
    self.auth_as(self.owner)

  def test_create_meal_under_a_restaurant(self):
    response = self.client.post(
      self.list_url,
      {"name": "Pasta", "description": "d", "price": "12.50", "restaurant": self.restaurant.pk,
       "is_blocked": True, "is_active": False},
      format="json",
    )

    self.assertEqual(response.status_code, 201)
    created = Meal.objects.get(pk=response.data["id"])
    self.assertEqual(created.restaurant, self.restaurant)
    self.assertEqual(created.price, Decimal("12.50"))
    self.assertFalse(created.is_blocked)
    self.assertTrue(created.is_active)

  def test_list_shows_active_meals_including_blocked(self):
    blocked = self.make_meal(self.restaurant, name="Blocked", is_blocked=True)
    deleted = self.make_meal(self.restaurant, name="Deleted", is_active=False)

    listed = ids(self.client.get(self.list_url))

    self.assertEqual(listed, {self.meal.pk, blocked.pk})
    self.assertNotIn(deleted.pk, listed)

  def test_put_and_patch_update_the_meal(self):
    put = self.client.put(self.url, {"name": "Put", "description": "d", "price": "5.00"}, format="json")
    self.assertEqual(put.status_code, 200)
    self.meal.refresh_from_db()
    self.assertEqual(self.meal.price, Decimal("5.00"))

    patch = self.client.patch(self.url, {"price": "6.00"}, format="json")
    self.assertEqual(patch.status_code, 200)

    self.meal.refresh_from_db()
    self.assertEqual((self.meal.name, self.meal.price), ("Put", Decimal("6.00")))

  def test_delete_is_a_soft_delete(self):
    response = self.client.delete(self.url)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["detail"], "Meal deleted successfully")

    self.meal.refresh_from_db()
    self.assertFalse(self.meal.is_active)

    self.assertEqual(self.client.get(self.url).status_code, 404)
    self.assertNotIn(self.meal.pk, ids(self.client.get(self.list_url)))
    self.assertEqual(self.client.delete(self.url).status_code, 404)

  def test_another_owners_restaurant_and_meals_are_not_found(self):
    others_list = f"{RESTAURANTS}{self.others_restaurant.pk}/meals/"
    others_url = f"{others_list}{self.others_meal.pk}/"
    body = {"name": "Hijacked", "description": "d", "price": "1.00"}

    self.assertEqual(self.client.get(others_list).status_code, 404)
    self.assertEqual(self.client.post(others_list, body, format="json").status_code, 404)
    self.assertEqual(self.client.get(others_url).status_code, 404)
    self.assertEqual(self.client.put(others_url, body, format="json").status_code, 404)
    self.assertEqual(self.client.patch(others_url, body, format="json").status_code, 404)
    self.assertEqual(self.client.delete(others_url).status_code, 404)

    self.others_meal.refresh_from_db()
    self.assertEqual(self.others_meal.name, "Not My Meal")
    self.assertTrue(self.others_meal.is_active)
    self.assertEqual(self.others_restaurant.meals.count(), 1)

  def test_own_meal_under_the_wrong_restaurant_is_not_found(self):
    second = self.make_restaurant(self.owner, name="Second")

    self.assertEqual(self.client.get(f"{RESTAURANTS}{second.pk}/meals/{self.meal.pk}/").status_code, 404)

  def test_blocked_meal_cannot_be_changed(self):
    original_name = self.meal.name
    self.meal.is_blocked = True
    self.meal.save()
    body = {"name": "Changed", "description": "d", "price": "1.00"}

    self.assertEqual(self.client.put(self.url, body, format="json").status_code, 403)
    self.assertEqual(self.client.patch(self.url, {"price": "1.00"}, format="json").status_code, 403)
    self.assertEqual(self.client.patch(self.url, {"is_blocked": False}, format="json").status_code, 403)
    self.assertEqual(self.client.delete(self.url).status_code, 403)

    self.meal.refresh_from_db()
    self.assertEqual(self.meal.name, original_name)
    self.assertTrue(self.meal.is_blocked)
    self.assertTrue(self.meal.is_active)

  def test_meals_of_a_blocked_restaurant_cannot_be_changed_or_added(self):
    self.restaurant.is_blocked = True
    self.restaurant.save()
    body = {"name": "New", "description": "d", "price": "1.00"}

    self.assertEqual(self.client.post(self.list_url, body, format="json").status_code, 403)
    self.assertEqual(self.client.put(self.url, body, format="json").status_code, 403)
    self.assertEqual(self.client.patch(self.url, {"price": "1.00"}, format="json").status_code, 403)
    self.assertEqual(self.client.delete(self.url).status_code, 403)

  def test_update_ignores_protected_fields(self):
    response = self.client.patch(
      self.url, {"price": "7.00", "is_blocked": True, "is_active": False, "restaurant": self.others_restaurant.pk},
      format="json",
    )

    self.assertEqual(response.status_code, 200)
    self.meal.refresh_from_db()
    self.assertEqual(self.meal.price, Decimal("7.00"))
    self.assertEqual(self.meal.restaurant, self.restaurant)
    self.assertTrue(self.meal.is_active)
    self.assertFalse(self.meal.is_blocked)

  def test_invalid_input_is_rejected(self):
    valid = {"name": "Pasta", "description": "d", "price": "5.00"}
    bad_bodies = [
      {**valid, "name": ""},
      {**valid, "price": "0"},
      {**valid, "price": "-1.00"},
      {**valid, "price": "abc"},
      {**valid, "price": "12345678.00"},
      {"name": "No price", "description": "d"},
    ]

    for body in bad_bodies:
      with self.subTest(body=body):
        self.assertEqual(self.client.post(self.list_url, body, format="json").status_code, 400)

    self.assertEqual(Meal.objects.filter(restaurant=self.restaurant).count(), 1)


class OwnerOrderTests(BaseAPITestCase):
  def setUp(self):
    self.owner = self.make_owner()
    self.other_owner = self.make_owner("other@test.com")
    self.alice = self.make_user("alice@test.com")
    self.bob = self.make_user("bob@test.com")

    self.restaurant = self.make_restaurant(self.owner)
    self.others_restaurant = self.make_restaurant(self.other_owner, name="Not Mine")
    self.meal = self.make_meal(self.restaurant)
    self.others_meal = self.make_meal(self.others_restaurant, name="Not My Meal")

    self.alice_order = self.make_order(self.alice, self.restaurant, [(self.meal, 2)])
    self.bob_order = self.make_order(self.bob, self.restaurant, [(self.meal, 1)])
    self.others_order = self.make_order(self.alice, self.others_restaurant, [(self.others_meal, 1)])
    self.auth_as(self.owner)

  def test_list_shows_only_orders_of_own_restaurants(self):
    response = self.client.get("/api/orders/")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["count"], 2)
    self.assertEqual(ids(response), {self.alice_order.pk, self.bob_order.pk})

  def test_detail_of_an_own_restaurants_order(self):
    response = self.client.get(f"/api/orders/{self.alice_order.pk}/")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["id"], self.alice_order.pk)
    self.assertEqual(response.data["items"][0]["quantity"], 2)
    self.assertEqual(len(response.data["status_history"]), 1)

  def test_detail_of_another_restaurants_order_is_not_found(self):
    self.assertEqual(self.client.get(f"/api/orders/{self.others_order.pk}/").status_code, 404)


class CustomerBrowsingTests(BaseAPITestCase):
  def setUp(self):
    self.owner = self.make_owner()
    self.restaurant = self.make_restaurant(self.owner)
    self.meal = self.make_meal(self.restaurant)
    self.customer = self.make_user("customer@test.com")
    self.auth_as(self.customer)

  def test_list_and_detail_show_a_visible_restaurant(self):
    listed = self.client.get(RESTAURANTS)
    detail = self.client.get(f"{RESTAURANTS}{self.restaurant.pk}/")

    self.assertEqual(listed.status_code, 200)
    self.assertIn(self.restaurant.pk, ids(listed))
    self.assertEqual(detail.status_code, 200)
    self.assertEqual(detail.data["name"], self.restaurant.name)

  def test_customer_sees_restaurants_of_every_owner(self):
    other = self.make_restaurant(self.make_owner("other@test.com"), name="Second Place")

    self.assertEqual(ids(self.client.get(RESTAURANTS)), {self.restaurant.pk, other.pk})

  def test_hidden_restaurants_are_not_listed_and_not_found(self):
    owner = self.make_owner(f"owner_blocked@test.com")
    restaurant = self.make_restaurant(owner, name="Hiding blocked owner")
    meal = self.make_meal(restaurant, name="Hidden meal")

    restaurant.is_blocked=True
    restaurant.save()

    base = f"{RESTAURANTS}{restaurant.pk}/"

    self.assertNotIn(restaurant.pk, ids(self.client.get(RESTAURANTS)))
    self.assertEqual(self.client.get(base).status_code, 404)
    self.assertEqual(self.client.get(f"{base}meals/").status_code, 404)
    self.assertEqual(self.client.get(f"{base}meals/{meal.pk}/").status_code, 404)

    restaurant.is_blocked = False
    restaurant.save()

    owner.is_blocked = True
    owner.save()

    self.assertNotIn(restaurant.pk, ids(self.client.get(RESTAURANTS)))
    self.assertEqual(self.client.get(base).status_code, 404)
    self.assertEqual(self.client.get(f"{base}meals/").status_code, 404)
    self.assertEqual(self.client.get(f"{base}meals/{meal.pk}/").status_code, 404)

  def test_blocked_and_deleted_meals_are_hidden(self):
    blocked = self.make_meal(self.restaurant, name="Blocked", is_blocked=True)
    deleted = self.make_meal(self.restaurant, name="Deleted", is_active=False)
    base = f"{RESTAURANTS}{self.restaurant.pk}/meals/"

    self.assertEqual(ids(self.client.get(base)), {self.meal.pk})
    self.assertEqual(self.client.get(f"{base}{blocked.pk}/").status_code, 404)
    self.assertEqual(self.client.get(f"{base}{deleted.pk}/").status_code, 404)

  def test_meal_detail_of_a_visible_meal(self):
    response = self.client.get(f"{RESTAURANTS}{self.restaurant.pk}/meals/{self.meal.pk}/")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["name"], self.meal.name)
    self.assertEqual(Decimal(response.data["price"]), self.meal.price)

  def test_meal_under_the_wrong_restaurant_is_not_found(self):
    second = self.make_restaurant(self.make_owner("other@test.com"), name="Second Place")

    self.assertEqual(self.client.get(f"{RESTAURANTS}{second.pk}/meals/{self.meal.pk}/").status_code, 404)

  def test_unknown_ids_are_not_found(self):
    self.assertEqual(self.client.get(f"{RESTAURANTS}999999/").status_code, 404)
    self.assertEqual(self.client.get(f"{RESTAURANTS}999999/meals/").status_code, 404)
    self.assertEqual(self.client.get(f"{RESTAURANTS}{self.restaurant.pk}/meals/999999/").status_code, 404)
