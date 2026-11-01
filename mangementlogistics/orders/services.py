# mangementlogistics/orders/services.py
from decimal import Decimal

from django.utils import timezone

from mangementlogistics.orders.constants import (
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
)
from mangementlogistics.orders.exceptions import (
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
)
from mangementlogistics.orders.models import Order
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User


def order_create(
    *,
    customer: User,
    sender_name: str,
    sender_phone: str,
    sender_address: str,
    receiver_name: str,
    receiver_phone: str,
    receiver_address: str,
    weight: Decimal = Decimal("1.0"),
    item_description: str = "",
    notes: str = "",
    cod_amount: Decimal = Decimal("0.00"),
    shipping_fee: Decimal = Decimal("0.00"),
    payment_method: str = OrderPaymentMethod.COD,
    driver: User | None = None,
) -> Order:
    """
    Creates a new delivery order.
    """
    if driver and getattr(driver, "role", None) != UserRole.DRIVER:
        raise DriverAssignmentError("Người dùng được chỉ định không phải là tài xế (Driver).")

    order = Order.objects.create(
        customer=customer,
        driver=driver,
        sender_name=sender_name,
        sender_phone=sender_phone,
        sender_address=sender_address,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        receiver_address=receiver_address,
        weight=weight,
        item_description=item_description,
        notes=notes,
        cod_amount=cod_amount,
        shipping_fee=shipping_fee,
        payment_method=payment_method,
        status=OrderStatus.PENDING,
    )
    return order


def order_update(*, order: Order, actor: User, **data) -> Order:
    """
    Updates order details with authorization checks.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_owner = order.customer_id == actor.id

    if not is_admin and not is_owner:
        raise OrderPermissionDeniedError("Bạn không có quyền chỉnh sửa đơn hàng này.")

    if not is_admin and not order.can_be_cancelled():
        raise OrderPermissionDeniedError(
            f"Không thể chỉnh sửa đơn hàng khi đang ở trạng thái '{order.get_status_display()}'."
        )

    # Disallow modifying non-editable critical fields directly via update
    data.pop("id", None)
    data.pop("tracking_number", None)
    data.pop("customer", None)
    data.pop("created_at", None)

    driver_id = data.pop("driver_id", None)
    if driver_id is not None:
        if not is_admin:
            raise OrderPermissionDeniedError("Chỉ quản trị viên mới có quyền gán hoặc đổi tài xế.")
        if driver_id:
            driver = User.objects.filter(id=driver_id, role=UserRole.DRIVER).first()
            if not driver:
                raise DriverAssignmentError("Tài xế không tồn tại hoặc không hợp lệ.")
            order.driver = driver
        else:
            order.driver = None

    for field, value in data.items():
        if hasattr(order, field):
            setattr(order, field, value)

    order.save()
    return order


def order_update_status(
    *,
    order: Order,
    new_status: str,
    actor: User,
    driver_id: int | None = None,
) -> Order:
    """
    Handles status transitions for an order.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_driver = getattr(actor, "role", None) == UserRole.DRIVER and order.driver_id == actor.id
    is_owner = order.customer_id == actor.id

    # Finished orders cannot be changed
    if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.RETURNED]:
        raise InvalidOrderStatusError(
            f"Đơn hàng đã ở trạng thái kết thúc '{order.get_status_display()}', không thể đổi trạng thái."
        )

    # Role-based status transition restrictions
    if not is_admin:
        if is_driver:
            # Drivers can update their assigned orders along delivery pipeline
            allowed_driver_statuses = [
                OrderStatus.PICKED_UP,
                OrderStatus.IN_TRANSIT,
                OrderStatus.DELIVERED,
                OrderStatus.RETURNED,
            ]
            if new_status not in allowed_driver_statuses:
                raise OrderPermissionDeniedError(f"Tài xế không có quyền chuyển sang trạng thái '{new_status}'.")
        elif is_owner:
            # Customers can only cancel
            if new_status != OrderStatus.CANCELLED:
                raise OrderPermissionDeniedError("Khách hàng chỉ có thể yêu cầu hủy đơn hàng.")
        else:
            raise OrderPermissionDeniedError("Bạn không có quyền cập nhật trạng thái đơn hàng này.")

    # Assign driver if provided
    if driver_id is not None and is_admin:
        driver = User.objects.filter(id=driver_id, role=UserRole.DRIVER).first()
        if not driver:
            raise DriverAssignmentError("Tài xế không hợp lệ.")
        order.driver = driver

    order.status = new_status

    if new_status == OrderStatus.DELIVERED:
        order.delivered_at = timezone.now()
        # If COD, assume money collected on delivery
        if order.payment_method == OrderPaymentMethod.COD:
            order.payment_status = OrderPaymentStatus.PAID

    order.save()
    return order


def order_cancel(*, order: Order, actor: User, reason: str = "") -> Order:
    """
    Cancels an order if it hasn't started transit.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_owner = order.customer_id == actor.id

    if not is_admin and not is_owner:
        raise OrderPermissionDeniedError("Bạn không có quyền hủy đơn hàng này.")

    if not order.can_be_cancelled():
        raise InvalidOrderStatusError(
            f"Không thể hủy đơn hàng đang ở trạng thái '{order.get_status_display()}'."
        )

    order.status = OrderStatus.CANCELLED
    if reason:
        order.notes = f"{order.notes}\n[Lý do hủy]: {reason}".strip()

    order.save()
    return order


def order_delete(*, order: Order, actor: User) -> None:
    """
    Deletes an order from the database.
    Only admin or owner (when still PENDING) can delete.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_owner = order.customer_id == actor.id and order.status == OrderStatus.PENDING

    if not is_admin and not is_owner:
        raise OrderPermissionDeniedError("Chỉ Quản trị viên hoặc người tạo (khi đơn chưa tiếp nhận) mới được xóa đơn hàng.")

    order.delete()
