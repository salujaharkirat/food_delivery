from .models import OrderStatus
from user.models import Role

ALLOWED_ORDER_STATUS_TRANSITIONS = {
  (OrderStatus.PLACED, OrderStatus.PROCESSING): {Role.OWNER},
  (OrderStatus.PLACED, OrderStatus.CANCELED): {Role.CUSTOMER, Role.OWNER},
  (OrderStatus.PROCESSING, OrderStatus.IN_ROUTE): {Role.OWNER},
  (OrderStatus.PROCESSING, OrderStatus.CANCELED): {Role.OWNER},
  (OrderStatus.IN_ROUTE, OrderStatus.DELIVERED): {Role.OWNER},
  (OrderStatus.DELIVERED, OrderStatus.RECEIVED): {Role.CUSTOMER},
}
