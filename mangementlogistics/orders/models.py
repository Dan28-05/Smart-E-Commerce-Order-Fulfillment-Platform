# mangementlogistics/orders/models.py
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
    ReturnFeePayer,
    ReturnReason,
    ReturnStatus,
    TripStatus,
    VehicleType,
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

    delivery_trip = models.ForeignKey(
        "DeliveryTrip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_orders",
        verbose_name=_("Chuyến giao hàng"),
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
    reconciliation = models.ForeignKey(
        "CODReconciliation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name=_("Kỳ đối soát COD"),
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
        """Total receivable amount (COD collection plus shipping fee)."""
        return self.cod_amount + self.shipping_fee

    @property
    def net_cod_amount(self):
        """Net receivable COD after deducting shipping fee."""
        return self.cod_amount - self.shipping_fee

    def can_be_cancelled(self) -> bool:
        """Check whether the order can be cancelled based on current lifecycle status."""
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


def generate_unique_reconciliation_code() -> str:
    """Generates unique reconciliation batch code like REC-20261107-A1B2"""
    date_part = timezone.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:4].upper()
    return f"REC-{date_part}-{random_part}"


class CODReconciliation(models.Model):
    """
    Financial statement aggregating delivered COD orders for shop payout settlement.
    """
    code = models.CharField(
        _("Mã bảng kê đối soát"),
        max_length=64,
        unique=True,
        default=generate_unique_reconciliation_code,
        editable=False,
        db_index=True,
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cod_reconciliations",
        verbose_name=_("Khách hàng / Chủ shop"),
    )
    total_orders_count = models.PositiveIntegerField(
        _("Số lượng đơn hàng"),
        default=0,
    )
    total_cod_amount = models.DecimalField(
        _("Tổng tiền thu hộ COD (VNĐ)"),
        max_digits=14,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )
    total_shipping_fees = models.DecimalField(
        _("Tổng cước phí vận chuyển (VNĐ)"),
        max_digits=14,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )
    net_payout_amount = models.DecimalField(
        _("Số tiền thực nhận / Quyết toán (VNĐ)"),
        max_digits=14,
        decimal_places=2,
        default=0.00,
    )
    status = models.CharField(
        _("Trạng thái đối soát"),
        max_length=32,
        choices=CODReconciliationStatus.choices,
        default=CODReconciliationStatus.PENDING,
        db_index=True,
    )
    notes = models.TextField(
        _("Ghi chú quyết toán"),
        blank=True,
        default="",
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_reconciliations",
        verbose_name=_("Người xử lý"),
    )
    created_at = models.DateTimeField(
        _("Ngày lập bảng kê"),
        auto_now_add=True,
        db_index=True,
    )
    confirmed_at = models.DateTimeField(
        _("Thời điểm xác nhận"),
        null=True,
        blank=True,
    )
    paid_at = models.DateTimeField(
        _("Thời điểm thanh toán"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Bảng kê đối soát COD")
        verbose_name_plural = _("Danh sách đối soát COD")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.code} - {self.customer.email} ({self.get_status_display()})"


def generate_unique_return_code() -> str:
    """Generates unique reverse logistics RMA code like RET-20261108-A1B2"""
    date_part = timezone.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:4].upper()
    return f"RET-{date_part}-{random_part}"


class OrderReturn(models.Model):
    """
    Reverse logistics return order (RMA) tracking returns, exchanges, refunds, and return transit.
    """
    return_code = models.CharField(
        _("Mã phiếu trả hàng"),
        max_length=64,
        unique=True,
        default=generate_unique_return_code,
        editable=False,
        db_index=True,
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="returns",
        verbose_name=_("Đơn hàng gốc"),
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requested_returns",
        verbose_name=_("Người yêu cầu hoàn trả"),
    )
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_return_tasks",
        verbose_name=_("Tài xế thu hồi bưu phẩm"),
    )
    reason = models.CharField(
        _("Lý do hoàn trả"),
        max_length=64,
        choices=ReturnReason.choices,
        default=ReturnReason.CUSTOMER_REFUSED,
    )
    reason_detail = models.TextField(
        _("Mô tả chi tiết nguyên nhân"),
        blank=True,
        default="",
    )
    status = models.CharField(
        _("Trạng thái xử lý trả hàng"),
        max_length=32,
        choices=ReturnStatus.choices,
        default=ReturnStatus.REQUESTED,
        db_index=True,
    )
    fee_payer = models.CharField(
        _("Bên chịu phí hoàn hàng"),
        max_length=32,
        choices=ReturnFeePayer.choices,
        default=ReturnFeePayer.SHOP,
    )
    return_shipping_fee = models.DecimalField(
        _("Cước phí chuyển hoàn (VNĐ)"),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )
    refund_amount = models.DecimalField(
        _("Số tiền hoàn trả (VNĐ)"),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )
    return_address = models.CharField(
        _("Địa chỉ nhận hàng hoàn (Kho / Shop)"),
        max_length=500,
        blank=True,
        default="",
    )
    pickup_address = models.CharField(
        _("Địa chỉ thu hồi hàng"),
        max_length=500,
        blank=True,
        default="",
    )
    notes = models.TextField(
        _("Ghi chú tiến trình hoàn trả"),
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(
        _("Ngày tạo yêu cầu"),
        auto_now_add=True,
        db_index=True,
    )
    approved_at = models.DateTimeField(
        _("Thời điểm duyệt"),
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(
        _("Thời điểm hoàn tất"),
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(
        _("Cập nhật lần cuối"),
        auto_now=True,
    )

    class Meta:
        verbose_name = _("Đơn hàng hoàn trả")
        verbose_name_plural = _("Danh sách đơn hàng hoàn trả")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.return_code} - {self.order.tracking_number} ({self.get_status_display()})"


def generate_unique_trip_code() -> str:
    """Generates unique dispatch delivery trip code like TRIP-20261110-A1B2"""
    date_part = timezone.now().strftime("%Y%m%d")
    random_part = uuid.uuid4().hex[:4].upper()
    return f"TRIP-{date_part}-{random_part}"


class DeliveryTrip(models.Model):
    """
    Logistics delivery run / trip manifest grouping multiple orders for driver dispatch and batch transit.
    """
    trip_code = models.CharField(
        _("Mã chuyến giao hàng"),
        max_length=64,
        unique=True,
        default=generate_unique_trip_code,
        editable=False,
        db_index=True,
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delivery_trips",
        verbose_name=_("Tài xế phụ trách"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_delivery_trips",
        verbose_name=_("Người tạo chuyến"),
    )
    route_name = models.CharField(
        _("Tên lộ trình / Tuyến giao"),
        max_length=255,
    )
    departure_hub = models.CharField(
        _("Kho xuất phát / Bưu cục"),
        max_length=255,
        default="Kho tổng điều phối",
    )
    vehicle_type = models.CharField(
        _("Phương tiện giao vận"),
        max_length=32,
        choices=VehicleType.choices,
        default=VehicleType.MOTORBIKE,
    )
    license_plate = models.CharField(
        _("Biển kiểm soát xe"),
        max_length=32,
        blank=True,
        default="",
    )
    status = models.CharField(
        _("Trạng thái chuyến"),
        max_length=32,
        choices=TripStatus.choices,
        default=TripStatus.PLANNED,
        db_index=True,
    )
    departure_time = models.DateTimeField(
        _("Thời điểm xuất bến"),
        null=True,
        blank=True,
    )
    completion_time = models.DateTimeField(
        _("Thời điểm hoàn thành"),
        null=True,
        blank=True,
    )
    notes = models.TextField(
        _("Ghi chú chuyến đi"),
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(
        _("Ngày lập chuyến"),
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        _("Cập nhật lần cuối"),
        auto_now=True,
    )

    class Meta:
        verbose_name = _("Chuyến giao hàng")
        verbose_name_plural = _("Danh sách chuyến giao hàng")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.trip_code} - {self.route_name} ({self.get_status_display()})"

    @property
    def total_orders_count(self) -> int:
        return self.trip_orders.count()

    @property
    def total_weight(self):
        return sum(order.weight for order in self.trip_orders.all())

    @property
    def total_cod_amount(self):
        return sum(order.cod_amount for order in self.trip_orders.all())

    @property
    def total_shipping_fee(self):
        return sum(order.shipping_fee for order in self.trip_orders.all())

    @property
    def delivered_orders_count(self) -> int:
        return self.trip_orders.filter(status=OrderStatus.DELIVERED).count()

    @property
    def failed_orders_count(self) -> int:
        return self.trip_orders.filter(status__in=[OrderStatus.CANCELLED, OrderStatus.RETURNED]).count()

    @property
    def completion_rate(self) -> int:
        total = self.total_orders_count
        if total == 0:
            return 0
        return int((self.delivered_orders_count / total) * 100)




