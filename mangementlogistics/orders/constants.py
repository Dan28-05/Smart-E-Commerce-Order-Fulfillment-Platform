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


class CODReconciliationStatus(models.TextChoices):
    PENDING = cast(str, ("PENDING", "Chờ đối soát"))
    CONFIRMED = cast(str, ("CONFIRMED", "Đã xác nhận đối soát"))
    PAID = cast(str, ("PAID", "Đã quyết toán"))


class ReturnStatus(models.TextChoices):
    REQUESTED = cast(str, ("REQUESTED", "Yêu cầu hoàn trả"))
    APPROVED = cast(str, ("APPROVED", "Đã duyệt yêu cầu"))
    PICKING_UP = cast(str, ("PICKING_UP", "Đang lấy hàng hoàn"))
    IN_RETURN_TRANSIT = cast(str, ("IN_RETURN_TRANSIT", "Đang chuyển hoàn về kho"))
    RETURNED_TO_SENDER = cast(str, ("RETURNED_TO_SENDER", "Đã hoàn trả thành công"))
    REJECTED = cast(str, ("REJECTED", "Từ chối hoàn trả"))
    CANCELLED = cast(str, ("CANCELLED", "Đã hủy yêu cầu"))


class ReturnReason(models.TextChoices):
    CUSTOMER_REFUSED = cast(str, ("CUSTOMER_REFUSED", "Người nhận từ chối nhận hàng"))
    WRONG_ITEM = cast(str, ("WRONG_ITEM", "Giao sai sản phẩm / mẫu mã"))
    DAMAGED = cast(str, ("DAMAGED", "Hàng hóa bể vỡ, hư hại khi vận chuyển"))
    UNREACHABLE = cast(str, ("UNREACHABLE", "Không thể liên lạc người nhận sau 3 lần"))
    CUSTOMER_REQUESTED = cast(str, ("CUSTOMER_REQUESTED", "Người mua đổi ý / Yêu cầu đổi trả"))
    OTHER = cast(str, ("OTHER", "Lý do khác"))


class ReturnFeePayer(models.TextChoices):
    SHOP = cast(str, ("SHOP", "Người gửi / Shop chịu phí hoàn"))
    CUSTOMER = cast(str, ("CUSTOMER", "Người nhận chịu phí"))
    CARRIER_COMPENSATE = cast(str, ("CARRIER_COMPENSATE", "Đơn vị vận chuyển bồi thường / Miễn phí"))




# ==============================================================================
# Shipping Calculation Constants & Regional Classifications
# ==============================================================================

REGION_NORTH = "NORTH"
REGION_CENTRAL = "CENTRAL"
REGION_SOUTH = "SOUTH"

PROVINCE_REGIONS = {
    # Northern Region
    "Hà Nội": REGION_NORTH,
    "Hải Phòng": REGION_NORTH,
    "Quảng Ninh": REGION_NORTH,
    "Bắc Giang": REGION_NORTH,
    "Bắc Kạn": REGION_NORTH,
    "Bắc Ninh": REGION_NORTH,
    "Cao Bằng": REGION_NORTH,
    "Điện Biên": REGION_NORTH,
    "Hà Giang": REGION_NORTH,
    "Hà Nam": REGION_NORTH,
    "Hải Dương": REGION_NORTH,
    "Hòa Bình": REGION_NORTH,
    "Hưng Yên": REGION_NORTH,
    "Lai Châu": REGION_NORTH,
    "Lạng Sơn": REGION_NORTH,
    "Lào Cai": REGION_NORTH,
    "Nam Định": REGION_NORTH,
    "Ninh Bình": REGION_NORTH,
    "Phú Thọ": REGION_NORTH,
    "Sơn La": REGION_NORTH,
    "Thái Bình": REGION_NORTH,
    "Thái Nguyên": REGION_NORTH,
    "Tuyên Quang": REGION_NORTH,
    "Vĩnh Phúc": REGION_NORTH,
    "Yên Bái": REGION_NORTH,
    # Central Region
    "Đà Nẵng": REGION_CENTRAL,
    "Thừa Thiên Huế": REGION_CENTRAL,
    "Quảng Nam": REGION_CENTRAL,
    "Quảng Ngãi": REGION_CENTRAL,
    "Bình Định": REGION_CENTRAL,
    "Phú Yên": REGION_CENTRAL,
    "Khánh Hòa": REGION_CENTRAL,
    "Ninh Thuận": REGION_CENTRAL,
    "Bình Thuận": REGION_CENTRAL,
    "Thanh Hóa": REGION_CENTRAL,
    "Nghệ An": REGION_CENTRAL,
    "Hà Tĩnh": REGION_CENTRAL,
    "Quảng Bình": REGION_CENTRAL,
    "Quảng Trị": REGION_CENTRAL,
    "Kon Tum": REGION_CENTRAL,
    "Gia Lai": REGION_CENTRAL,
    "Đắk Lắk": REGION_CENTRAL,
    "Đắk Nông": REGION_CENTRAL,
    "Lâm Đồng": REGION_CENTRAL,
    # Southern Region
    "TP. Hồ Chí Minh": REGION_SOUTH,
    "Cần Thơ": REGION_SOUTH,
    "Bình Dương": REGION_SOUTH,
    "Đồng Nai": REGION_SOUTH,
    "Bà Rịa - Vũng Tàu": REGION_SOUTH,
    "Long An": REGION_SOUTH,
    "Tiền Giang": REGION_SOUTH,
    "Bến Tre": REGION_SOUTH,
    "Trà Vinh": REGION_SOUTH,
    "Vĩnh Long": REGION_SOUTH,
    "Đồng Tháp": REGION_SOUTH,
    "An Giang": REGION_SOUTH,
    "Kiên Giang": REGION_SOUTH,
    "Hậu Giang": REGION_SOUTH,
    "Sóc Trăng": REGION_SOUTH,
    "Bạc Liêu": REGION_SOUTH,
    "Cà Mau": REGION_SOUTH,
    "Tây Ninh": REGION_SOUTH,
    "Bình Phước": REGION_SOUTH,
}

VIETNAM_PROVINCES = list(PROVINCE_REGIONS.keys())

