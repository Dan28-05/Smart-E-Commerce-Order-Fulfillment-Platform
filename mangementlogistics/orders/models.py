# mangementlogistics/orders/models.py
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from mangementlogistics.orders.constants import (
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
)


def generate_unique_tracking_number() -> str:
    """Generates unique tracking code like ORD-20261101-A1B2C3"""
    date_part = timezone.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"ORD-{date_part}-{random_part}"


class Order(models.Model):
    """
    Logistics Order entity storing delivery routing, pricing, customer & driver details.
    """
    tracking_number = models.CharField(
        _("Mã vận đơn"),
        max_length=64,
        unique=True,
        default=generate_unique_tracking_number,
        editable=False,
        db_index=True,
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name=_("Khách hàng"),
    )

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
        verbose_name=_("Tài xế phụ trách"),
    )

    # Sender info
    sender_name = models.CharField(_("Tên người gửi"), max_length=255)
    sender_phone = models.CharField(_("Số điện thoại người gửi"), max_length=32)
    sender_address = models.CharField(_("Địa chỉ gửi hàng"), max_length=500)

    # Receiver info
    receiver_name = models.CharField(_("Tên người nhận"), max_length=255)
    receiver_phone = models.CharField(_("Số điện thoại người nhận"), max_length=32)
    receiver_address = models.CharField(_("Địa chỉ nhận hàng"), max_length=500)

    # Package details
    weight = models.DecimalField(
        _("Trọng lượng (kg)"),
        max_digits=8,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.01)],
    )
    item_description = models.TextField(_("Mô tả hàng hóa"), blank=True, default="")
    notes = models.TextField(_("Ghi chú giao hàng"), blank=True, default="")

    # Pricing & Payment
    cod_amount = models.DecimalField(
        _("Tiền thu hộ COD (VNĐ)"),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )
    shipping_fee = models.DecimalField(
        _("Cước phí vận chuyển (VNĐ)"),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )
    payment_method = models.CharField(
        _("Phương thức thanh toán"),
        max_length=32,
        choices=OrderPaymentMethod.choices,
        default=OrderPaymentMethod.COD,
    )
    payment_status = models.CharField(
        _("Trạng thái thanh toán"),
        max_length=32,
        choices=OrderPaymentStatus.choices,
        default=OrderPaymentStatus.UNPAID,
    )

    # Delivery status
    status = models.CharField(
        _("Trạng thái đơn hàng"),
        max_length=32,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )

    # Timestamps
    created_at = models.DateTimeField(_("Ngày tạo"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("Cập nhật lần cuối"), auto_now=True)
    delivered_at = models.DateTimeField(_("Thời điểm giao thành công"), null=True, blank=True)

    class Meta:
        verbose_name = _("Đơn hàng")
        verbose_name_plural = _("Danh sách đơn hàng")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.tracking_number} - {self.receiver_name} ({self.get_status_display()})"

    @property
    def total_amount(self):
        """Tổng số tiền (COD + Cước phí)"""
        return self.cod_amount + self.shipping_fee

    def can_be_cancelled(self) -> bool:
        """Kiểm tra đơn hàng có thể hủy được hay không"""
        return self.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]


class OrderTrackingHistory(models.Model):
    """
    Logistics tracking event history capturing milestones, locations, status updates, and notes.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="tracking_history",
        verbose_name=_("Đơn hàng"),
    )
    status = models.CharField(
        _("Trạng thái"),
        max_length=32,
        choices=OrderStatus.choices,
    )
    location = models.CharField(
        _("Vị trí / Bưu cục / Kho"),
        max_length=255,
        blank=True,
        default="",
    )
    note = models.TextField(
        _("Mô tả / Ghi chú hành trình"),
        blank=True,
        default="",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_tracking_events",
        verbose_name=_("Người ghi nhận"),
    )
    created_at = models.DateTimeField(
        _("Thời gian ghi nhận"),
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        verbose_name = _("Lịch sử hành trình")
        verbose_name_plural = _("Lịch sử hành trình")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order.tracking_number} - {self.get_status_display()} ({self.created_at.strftime('%d/%m/%Y %H:%M')})"

