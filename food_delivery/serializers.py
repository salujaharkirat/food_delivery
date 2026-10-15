from rest_framework import serializers

from .models import Restaurant, Meal, OrderItem, Order, OrderStatusHistory, OrderStatus

class MealSerializer(serializers.ModelSerializer):
  class Meta:
    model = Meal
    fields = ('id', 'description', 'price', 'name')
    read_only_fields = fields


class RestaurantSerializer(serializers.ModelSerializer):
  class Meta:
    model = Restaurant
    fields = ('id', 'name', 'description')
    read_only_fields = fields

class OrderItemInputSerializer(serializers.Serializer):
  meal_id = serializers.IntegerField()
  quantity = serializers.IntegerField(min_value=1)

class OrderItemOutputSerializer(serializers.ModelSerializer):
  class Meta:
    model = OrderItem
    fields = ('meal_id', 'quantity', 'unit_price')

class OrderStatusSerializer(serializers.Serializer):
  status = serializers.ChoiceField(choices=OrderStatus.choices)

class OrderStatusHistoryOutSerializer(serializers.ModelSerializer):
  class Meta:
    model = OrderStatusHistory
    fields = ('status', 'changed_by', 'changed_at')

class OrderOutputSerializer(serializers.ModelSerializer):
  items = OrderItemOutputSerializer(many=True, read_only=True)
  status_history = OrderStatusHistoryOutSerializer(many=True, read_only=True)
  
  class Meta:
    model = Order
    fields = ('id', 'status', 'restaurant_id', 'coupon_id', 'subtotal', 'discount_amount',
              'tip_amount', 'total_amount', 'created_at', 'items', 'status_history')
    read_only_fields = fields

class OrderSerializer(serializers.Serializer):
  restaurant_id = serializers.IntegerField()
  items = OrderItemInputSerializer(many=True, allow_empty=False)
  tip_amount = serializers.DecimalField(required=False, max_digits=6, decimal_places=2, default=0, min_value=0)
  coupon_code = serializers.CharField(required=False)


