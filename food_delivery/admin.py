from django.contrib import admin

from .models import *

# Register your models here.
admin.site.register([Restaurant, Meal, Order, OrderItem, OrderStatusHistory, Coupon])
