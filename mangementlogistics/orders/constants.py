# mangementlogistics/orders/constants.py
from typing import cast

from django.db import models


class OrderStatus(models.TextChoices):
    PENDING = cast(str, ("PENDING", "Chờ tiếp nhận"))
    CONFIRMED = cast(str, ("CONFIRMED", "Đã xác nhận"))
    PICKED_UP = cast(str, ("PICKED_UP", "Đã lấy hàng"))
    IN_TRANSIT = cast(str, ("IN_TRANSIT", "Đang vận chuyển"))
    DELIVERED = cast(str, ("DELIVERED", "Giao thành công"))
    CANCELLED = cast(str, ("CANCELLED", "Đã hủy"))
    RETURNED = cast(str, ("RETURNED", "Trả hàng"))


class OrderPaymentMethod(models.TextChoices):
    COD = cast(str, ("COD", "Thanh toán khi nhận hàng (COD)"))
    BANK_TRANSFER = cast(str, ("BANK_TRANSFER", "Chuyển khoản"))


class OrderPaymentStatus(models.TextChoices):
    UNPAID = cast(str, ("UNPAID", "Chưa thanh toán"))
    PAID = cast(str, ("PAID", "Đã thanh toán"))
