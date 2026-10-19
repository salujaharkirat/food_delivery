from decimal import Decimal
from datetime import timedelta

from user.models import Role
from food_delivery.models import Restaurant, Order, Meal, OrderStatus, OrderItem, \
OrderStatusHistory

from config.base_test import BaseAPITestCase

RESTAURANTS = "/api/restaurants/"
ORDERS = "/api/orders/"

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

class PlaceOrderTests(BaseAPITestCase):
  def setUp(self):
    self.owner = self.make_owner()
    self.restaurant = self.make_restaurant(self.owner)
    self.curry = self.make_meal(self.restaurant, name="Curry", price="10.00")
    self.rice = self.make_meal(self.restaurant, name="rice", price="5.50")
    self.customer = self.make_user("customer@test.com")
    self.auth_as(self.customer)

  def body(self, **extra):
    body = {
      "restaurant_id": self.restaurant.pk,
      "items": [{"meal_id": self.curry.pk, "quantity": 3}, {"meal_id": self.rice.pk, "quantity": 2}],
      "tip_amount": "3.00"
    }

    body.update(extra)
    return body

  def place(self, **extra):
    return self.client.post(ORDERS, self.body(**extra), format="json")

  def assert_rejected(self, response, expected=400):
    self.assertEqual(response.status_code, expected, response.data)
    self.assertEqual(Order.objects.count(), 0)
    self.assertEqual(OrderItem.objects.count(), 0)

  def test_place_order_calculates_totals_and_stores_everything(self):
    response = self.place()

    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data["status"], "placed")
    self.assertEqual(response.data["restaurant_id"], self.restaurant.pk)
    self.assertEqual(response.data["subtotal"], "41.00")
    self.assertEqual(response.data["tip_amount"], "3.00")
    self.assertEqual(response.data["discount_amount"], "0.00")
    self.assertEqual(response.data["total_amount"], "44.00")
    self.assertIsNone(response.data["coupon_id"])

    order = Order.objects.get(id=response.data["id"])
    self.assertEqual(order.customer, self.customer)
    self.assertEqual(order.items.count(), 2)

    prices = {item.meal_id: (item.quantity, item.unit_price) for item in order.items.all()}
    self.assertEqual(prices, {self.curry.pk: (3, Decimal("10.00")), self.rice.pk: (2, Decimal("5.50"))})

  def test_tip_is_optional_and_defaults_to_zero(self):
    body = self.body()
    del body["tip_amount"]

    response = self.client.post(ORDERS, body, format="json")

    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data["tip_amount"], "0.00")
    self.assertEqual(response.data["total_amount"], "41.00")

  def test_first_status_history_row_is_written(self):
    order_id = self.place().data["id"]

    history = self.client.get(f"{ORDERS}{order_id}/").data["status_history"]

    self.assertEqual(len(history), 1)
    self.assertEqual(history[0]["status"], OrderStatus.PLACED)
    self.assertEqual(history[0]["changed_by"], self.customer.pk)

  def test_client_cannot_set_computed_fields(self):
    items = [{"meal_id": self.curry.pk, "quantity": 1, "unit_price": "0.01"}]
    response = self.place(
      items=items, status="delivered", subtotal="0.01", discount_amount="5.00", total_amount="0.01",
      customer=self.make_user("other@test.com").pk,
    )

    self.assertEqual(response.status_code, 201)
    order = Order.objects.get()
    self.assertEqual(order.status, OrderStatus.PLACED)
    self.assertEqual(order.customer, self.customer)
    self.assertEqual((order.subtotal, order.discount_amount, order.total_amount), (Decimal("10.00"), Decimal("0"), Decimal("13.00")))
    self.assertEqual(order.items.get().unit_price, Decimal("10.00"))

  def test_coupon_applies_a_whole_percentage_discount(self):
    coupon = self.make_coupon(code="SAVE10", percentage="10")

    response = self.place(coupon_code="SAVE10")

    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data["coupon_id"], coupon.pk)
    self.assertEqual(response.data["discount_amount"], "4.10")
    self.assertEqual(response.data["total_amount"], "39.90")

  def test_discount_rounds_half_up_to_two_decimals(self):
    self.make_coupon(code="QUARTER", percentage="25")
    cheap = self.make_meal(self.restaurant, name="Odd price", price="10.10")

    response = self.place(items=[{"meal_id": cheap.pk, "quantity": 1}], tip_amount="0", coupon_code="QUARTER")

    self.assertEqual(response.data["discount_amount"], "2.53")
    self.assertEqual(response.data["total_amount"], "7.57")

  def test_bad_coupons_are_rejected(self):
    c1 = self.make_coupon(code="EXPIRED", expires_in=timedelta(seconds=-1))
    c2 = self.make_coupon(code="INACTIVE", is_active=False)

    response = self.place(coupon_code=c1.code)
    self.assert_rejected(response)

    response = self.place(coupon_code=c2.code)
    self.assert_rejected(response)

  def test_meal_from_another_restaurant_is_rejected(self):
    elsewhere = self.make_meal(self.make_restaurant(self.make_owner("other@test.com"), name="Elsewhere"), name="Far away")

    self.assert_rejected(self.place(items=[{"meal_id": elsewhere.pk, "quantity": 1}]))
    self.assert_rejected(self.place(items=[
      {"meal_id": self.curry.pk, "quantity": 1}, {"meal_id": elsewhere.pk, "quantity": 1},
    ]))

  def test_invalid_items_are_rejected(self):
    meal_id = self.curry.pk
    bad_items = {
      "empty_list": [],
      "quantity_zero": [{"meal_id": meal_id, "quantity": 0}],
      "fractional_quantity": [{"meal_id": meal_id, "quantity": 1.5}],
      "missing_quantity": [{"meal_id": meal_id}],
      "missing_meal": [{"quantity": 1}],
      "unknown_meal": [{"meal_id": 999999, "quantity": 1}],
      "duplicate_meal": [{"meal_id": meal_id, "quantity": 1}, {"meal_id": meal_id, "quantity": 2}],
    }

    for _, items in bad_items.items():
      with self.subTest():
        self.assert_rejected(self.place(items=items))

  def test_unavailable_meals_and_restaurants_are_rejected(self):
    inactive_meal = self.make_meal(self.restaurant, is_active=False)
    blocked_meal = self.make_meal(self.restaurant, is_blocked=True)
    meal = self.make_meal(self.restaurant, name="Test meal", price="5.00")

    self.assert_rejected(self.place(items=[
      {"meal_id": inactive_meal.pk, "quantity": 1}
    ]))

    self.assert_rejected(self.place(items=[
      {"meal_id": blocked_meal.pk, "quantity": 1}
    ]))

    self.restaurant.is_blocked = True
    self.restaurant.save()

    self.assert_rejected(self.place(items=[
      {"meal_id": meal.pk, "quantity": 1}
    ]))

    self.restaurant.is_blocked = False
    self.restaurant.is_active = False
    self.restaurant.save()

    self.assert_rejected(self.place(items=[
      {"meal_id": meal.pk, "quantity": 1}
    ]))

    self.restaurant.is_blocked = False
    self.restaurant.is_active = True
    self.restaurant.save()

    response = self.place(items=[
      {"meal_id": meal.pk, "quantity": 2}
    ])

    self.assertEqual(response.status_code, 201)

class CustomerOrderViewTests(BaseAPITestCase):
  def setUp(self):
    self.owner = self.make_owner()
    self.restaurant = self.make_restaurant(self.owner)
    self.meal = self.make_meal(self.restaurant)
    self.alice = self.make_user("alice@test.com")
    self.bob = self.make_user("bob@test.com")

    self.alice_first_order = self.make_order(self.alice, self.restaurant, [(self.meal, 1)])
    self.alice_second_order = self.make_order(self.alice, self.restaurant, [(self.meal, 2)])
    self.bob_order = self.make_order(self.bob, self.restaurant, [(self.meal, 1)])
    self.auth_as(self.alice)

  def test_list_shows_only_own_orders_newest_first(self):
    response = self.client.get(ORDERS)

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["count"], 2)
    self.assertEqual([order["id"] for order in response.data["results"]], [self.alice_second_order.pk, self.alice_first_order.pk])

  def test_detail_of_own_order(self):
    response = self.client.get(f"{ORDERS}{self.alice_second_order.pk}/")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["id"], self.alice_second_order.pk)
    self.assertEqual(response.data["items"][0]["quantity"], 2)

  def test_another_customers_order_is_not_found(self):
    self.assertEqual(self.client.get(f"{ORDERS}{self.bob_order.pk}/").status_code, 404)

  def test_unknown_order_is_not_found(self):
    self.assertEqual(self.client.get(f"{ORDERS}999999/").status_code, 404)

  def test_old_orders_survive_deleting_the_restaurant_and_meal(self):
    self.meal.is_active = False
    self.meal.save()
    self.restaurant.is_active = False
    self.restaurant.save()

    listed = self.client.get(ORDERS)
    detail = self.client.get(f"{ORDERS}{self.alice_second_order.pk}/")

    self.assertEqual(listed.data["count"], 2)
    self.assertEqual(detail.status_code, 200)
    self.assertEqual(detail.data["items"][0]["meal_id"], self.meal.pk)
    self.assertEqual(detail.data["items"][0]["unit_price"], "10.00")

class OrderStatusTests(BaseAPITestCase):
  def setUp(self):
    self.owner = self.make_owner()
    self.customer = self.make_user("customer@test.com")
    self.admin = self.make_admin()
    self.restaurant = self.make_restaurant(self.owner)
    self.meal = self.make_meal(self.restaurant)
    self.users = {Role.CUSTOMER: self.customer, Role.OWNER: self.owner, Role.ADMIN: self.admin}
    self.tokens = {role: self.login(user) for role, user in self.users.items()}

  def new_order(self, status=OrderStatus.PLACED):
    return self.make_order(self.customer, self.restaurant, [(self.meal, 1)], status=status)

  def post_status(self, order, new_status, token):
    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return self.client.post(f"/api/orders/{order.pk}/status/", {"status": new_status}, format="json")

  def change(self, order, new_status, role):
    return self.post_status(order, new_status, self.tokens[role])

  def change_as(self, order, new_status, user):
    return self.post_status(order, new_status, self.login(user))

  def history(self, order):
    return list(OrderStatusHistory.objects.filter(order=order).values_list("status", flat=True))

  def test_customer_cannot_cancel_once_owner_has_started(self):
    order = self.new_order()
    response = self.change(order, OrderStatus.PROCESSING, Role.OWNER)
    self.assertEqual(response.status_code, 200)
    response = self.change(order, OrderStatus.CANCELED, Role.CUSTOMER)
    self.assertEqual(response.status_code, 403)
    order.refresh_from_db()
    self.assertEqual(order.status, OrderStatus.PROCESSING)

  def test_unknown_order_is_not_found(self):
    self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens[Role.OWNER]}")
    self.assertEqual(self.client.post("/api/orders/999999/status/", {"status": OrderStatus.PROCESSING}, format="json").status_code, 404)

  def test_another_owner_cannot_change_the_order(self):
    stranger = self.make_owner("stranger@test.com")
    order = self.new_order()
    response = self.change_as(order, OrderStatus.PROCESSING, stranger)

    self.assertEqual(response.status_code, 404)
    order.refresh_from_db()
    self.assertEqual(order.status, OrderStatus.PLACED)
    self.assertEqual(self.history(order), [OrderStatus.PLACED])

  def test_full_lifecycle_is_recorded_in_history(self):
    order = self.new_order()
    steps = [
      (Role.OWNER, OrderStatus.PROCESSING),
      (Role.OWNER, OrderStatus.IN_ROUTE),
      (Role.OWNER, OrderStatus.DELIVERED),
      (Role.CUSTOMER, OrderStatus.RECEIVED),
    ]

    for role, status in steps:
      self.assertEqual(self.change(order, status, role).status_code, 200)

    order.refresh_from_db()
    self.assertEqual(order.status, OrderStatus.RECEIVED)
    self.assertEqual(len(self.history(order)), 5)
