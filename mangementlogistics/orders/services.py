# mangementlogistics/orders/services.py
from decimal import Decimal
import math

from django.db import transaction
from django.utils import timezone

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderPaymentMethod,
    OrderPaymentStatus,
    OrderStatus,
    PROVINCE_REGIONS,
    REGION_CENTRAL,
    REGION_NORTH,
    REGION_SOUTH,
    ReturnFeePayer,
    ReturnReason,
    ReturnStatus,
)
from mangementlogistics.orders.exceptions import (
    CODReconciliationError,
    DriverAssignmentError,
    InvalidOrderStatusError,
    OrderPermissionDeniedError,
    OrderReturnError,
)
from mangementlogistics.orders.models import (
    CODReconciliation,
    Order,
    OrderReturn,
    OrderTrackingHistory,
)
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User


def order_add_tracking_event(
    *,
    order: Order,
    status: str,
    location: str = "",
    note: str = "",
    actor: User | None = None,
) -> OrderTrackingHistory:
    """
    Creates and records a tracking history milestone for the order.
    """
    return OrderTrackingHistory.objects.create(
        order=order,
        status=status,
        location=location.strip(),
        note=note.strip(),
        actor=actor,
    )



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

    # Record initial tracking milestone
    order_add_tracking_event(
        order=order,
        status=OrderStatus.PENDING,
        location=sender_address,
        note="Đơn hàng được khởi tạo thành công trên hệ thống.",
        actor=customer,
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
    location: str = "",
    note: str = "",
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

    # Record tracking milestone
    default_notes = {
        OrderStatus.CONFIRMED: "Đơn hàng đã được xác nhận và chờ phân bổ điều phối.",
        OrderStatus.PICKED_UP: "Tài xế đã tiếp nhận bưu phẩm từ người gửi.",
        OrderStatus.IN_TRANSIT: "Bưu phẩm đang được vận chuyển đến người nhận.",
        OrderStatus.DELIVERED: "Bưu phẩm đã được phát thành công cho người nhận.",
        OrderStatus.RETURNED: "Bưu phẩm đã hoàn trả về người gửi.",
    }
    event_note = note or default_notes.get(
        new_status, f"Đơn hàng chuyển sang trạng thái: {order.get_status_display()}"
    )
    order_add_tracking_event(
        order=order,
        status=new_status,
        location=location,
        note=event_note,
        actor=actor,
    )

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

    # Record cancellation event
    order_add_tracking_event(
        order=order,
        status=OrderStatus.CANCELLED,
        location="",
        note=f"Đơn hàng đã bị hủy. {f'Lý do: {reason}' if reason else ''}".strip(),
        actor=actor,
    )

    return order


def order_add_checkpoint(
    *,
    order: Order,
    location: str,
    note: str,
    actor: User,
) -> OrderTrackingHistory:
    """
    Allows driver or admin to record a custom transit checkpoint/milestone along the route.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_driver = getattr(actor, "role", None) == UserRole.DRIVER and order.driver_id == actor.id

    if not is_admin and not is_driver:
        raise OrderPermissionDeniedError("Chỉ tài xế phụ trách hoặc quản trị viên mới được cập nhật hành trình.")

    return order_add_tracking_event(
        order=order,
        status=order.status,
        location=location,
        note=note,
        actor=actor,
    )



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


def calculate_shipping_rates(
    *,
    sender_province: str,
    receiver_province: str,
    weight: Decimal | float | int,
    length: Decimal | float | int = 0,
    width: Decimal | float | int = 0,
    height: Decimal | float | int = 0,
    cod_amount: Decimal | float | int = 0,
) -> dict:
    """
    Calculates logistics shipping costs, billable weight, route classification,
    and estimated delivery times across service tiers (Economy, Standard, Express).
    """
    actual_weight = Decimal(str(weight or 1.0))
    if actual_weight <= Decimal("0"):
        actual_weight = Decimal("0.01")

    # Calculate volumetric weight: (L x W x H in cm) / 5000
    len_val = float(length or 0)
    wid_val = float(width or 0)
    hgt_val = float(height or 0)

    if len_val > 0 and wid_val > 0 and hgt_val > 0:
        volumetric_calc = round((len_val * wid_val * hgt_val) / 5000.0, 2)
        volumetric_weight = Decimal(str(volumetric_calc))
    else:
        volumetric_weight = Decimal("0.00")

    chargeable_weight = max(actual_weight, volumetric_weight)
    is_volumetric = volumetric_weight > actual_weight

    sender = sender_province.strip()
    receiver = receiver_province.strip()

    # Route classification
    sender_reg = PROVINCE_REGIONS.get(sender, REGION_NORTH)
    receiver_reg = PROVINCE_REGIONS.get(receiver, REGION_SOUTH)

    if sender.lower() == receiver.lower() or (sender in PROVINCE_REGIONS and receiver in PROVINCE_REGIONS and sender == receiver):
        route_type = "INTRA_PROVINCE"
        route_label = "Nội tỉnh"
        # Base: 18,000 VND up to 2.0 kg; +3,000 VND / additional 0.5 kg
        base_threshold = Decimal("2.0")
        base_cost = 18000
        step_weight = 0.5
        step_cost = 3000
        sla_standard = "Trong ngày (12 - 24 giờ)"
        sla_express = "2 - 4 giờ (Hỏa tốc nội thành)"
        sla_economy = "1 - 2 ngày"
    elif sender_reg == receiver_reg:
        route_type = "INTRA_REGION"
        region_name = "Miền Bắc" if sender_reg == REGION_NORTH else ("Miền Trung" if sender_reg == REGION_CENTRAL else "Miền Nam")
        route_label = f"Nội miền ({region_name})"
        # Base: 30,000 VND up to 1.0 kg; +5,000 VND / additional 0.5 kg
        base_threshold = Decimal("1.0")
        base_cost = 30000
        step_weight = 0.5
        step_cost = 5000
        sla_standard = "24 - 48 giờ"
        sla_express = "12 - 24 giờ"
        sla_economy = "2 - 3 ngày"
    else:
        route_type = "INTER_REGION"
        route_label = "Liên miền (Bắc - Trung - Nam)"
        # Base: 45,000 VND up to 0.5 kg; +8,000 VND / additional 0.5 kg
        base_threshold = Decimal("0.5")
        base_cost = 45000
        step_weight = 0.5
        step_cost = 8000
        sla_standard = "2 - 4 ngày"
        sla_express = "24 - 36 giờ (Đường bay ưu tiên)"
        sla_economy = "4 - 6 ngày (Đường bộ)"

    # Base pricing calculation
    if chargeable_weight <= base_threshold:
        calculated_base_fee = base_cost
    else:
        extra_weight = float(chargeable_weight - base_threshold)
        extra_steps = math.ceil(extra_weight / step_weight)
        calculated_base_fee = base_cost + (extra_steps * step_cost)

    # Insurance / COD fee (0.5% above 3,000,000 VND)
    cod_decimal = Decimal(str(cod_amount or 0))
    if cod_decimal > Decimal("3000000"):
        insurance_fee = int(round(float(cod_decimal - Decimal("3000000")) * 0.005))
    else:
        insurance_fee = 0

    # Service tiers:
    # 1. Economy: 0.8x base fee (rounded to thousands)
    economy_shipping = int(round(calculated_base_fee * 0.8 / 1000.0) * 1000)
    # 2. Standard: 1.0x base fee
    standard_shipping = int(round(calculated_base_fee * 1.0 / 1000.0) * 1000)
    # 3. Express: 1.45x base fee
    express_shipping = int(round(calculated_base_fee * 1.45 / 1000.0) * 1000)

    plans = [
        {
            "code": "ECONOMY",
            "name": "Giao Tiết Kiệm",
            "tag": "Tiết kiệm 20%",
            "badge_class": "bg-success",
            "icon": "bi-piggy-bank-fill",
            "shipping_fee": economy_shipping,
            "insurance_fee": insurance_fee,
            "total_fee": economy_shipping + insurance_fee,
            "estimated_delivery": sla_economy,
            "description": "Chi phí rẻ nhất, thích hợp cho kiện hàng cồng kềnh và hàng hóa không gấp.",
        },
        {
            "code": "STANDARD",
            "name": "Giao Tiêu Chuẩn",
            "tag": "Khuyên dùng",
            "badge_class": "bg-primary",
            "icon": "bi-truck",
            "shipping_fee": standard_shipping,
            "insurance_fee": insurance_fee,
            "total_fee": standard_shipping + insurance_fee,
            "estimated_delivery": sla_standard,
            "description": "Cân bằng hoàn hảo giữa tốc độ giao hàng ổn định và chi phí vận chuyển.",
        },
        {
            "code": "EXPRESS",
            "name": "Giao Hỏa Tốc",
            "tag": "Nhanh nhất",
            "badge_class": "bg-danger",
            "icon": "bi-lightning-charge-fill",
            "shipping_fee": express_shipping,
            "insurance_fee": insurance_fee,
            "total_fee": express_shipping + insurance_fee,
            "estimated_delivery": sla_express,
            "description": "Vận chuyển ưu tiên cao nhất, giao ngay trong ngày hoặc đường bay kết nối.",
        },
    ]

    return {
        "sender_province": sender,
        "receiver_province": receiver,
        "actual_weight": float(actual_weight),
        "volumetric_weight": float(volumetric_weight),
        "chargeable_weight": float(chargeable_weight),
        "is_volumetric": is_volumetric,
        "route_type": route_type,
        "route_label": route_label,
        "base_cost": calculated_base_fee,
        "cod_amount": float(cod_decimal),
        "insurance_fee": insurance_fee,
        "plans": plans,
    }


def cod_reconciliation_generate(
    *,
    customer: User,
    actor: User,
    notes: str = "",
) -> CODReconciliation:
    """
    Generates a COD financial reconciliation statement for delivered, unreconciled COD orders.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_self = actor.id == customer.id

    if not is_admin and not is_self:
        raise OrderPermissionDeniedError("Bạn không có quyền lập kỳ đối soát cho khách hàng này.")

    with transaction.atomic():
        eligible_orders = list(
            Order.objects.select_for_update().filter(
                customer=customer,
                status=OrderStatus.DELIVERED,
                payment_method=OrderPaymentMethod.COD,
                reconciliation__isnull=True,
            )
        )

        if not eligible_orders:
            raise CODReconciliationError(
                "Không có đơn hàng COD giao thành công nào đang chờ đối soát cho tài khoản này."
            )

        total_orders_count = len(eligible_orders)
        total_cod = sum(o.cod_amount for o in eligible_orders)
        total_shipping = sum(o.shipping_fee for o in eligible_orders)
        net_payout = total_cod - total_shipping

        reconciliation = CODReconciliation.objects.create(
            customer=customer,
            total_orders_count=total_orders_count,
            total_cod_amount=total_cod,
            total_shipping_fees=total_shipping,
            net_payout_amount=net_payout,
            status=CODReconciliationStatus.PENDING,
            notes=notes.strip(),
            processed_by=actor if is_admin else None,
        )

        order_ids = [o.id for o in eligible_orders]
        Order.objects.filter(id__in=order_ids).update(reconciliation=reconciliation)

        return reconciliation


def cod_reconciliation_confirm(
    *,
    reconciliation: CODReconciliation,
    actor: User,
    notes: str = "",
) -> CODReconciliation:
    """
    Confirms the reconciliation statement by an admin, locking the figures for payment.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    if not is_admin:
        raise OrderPermissionDeniedError("Chỉ Quản trị viên mới có quyền xác nhận bảng kê đối soát COD.")

    if reconciliation.status != CODReconciliationStatus.PENDING:
        raise CODReconciliationError(
            f"Không thể xác nhận bảng kê đang ở trạng thái '{reconciliation.get_status_display()}'."
        )

    reconciliation.status = CODReconciliationStatus.CONFIRMED
    reconciliation.confirmed_at = timezone.now()
    reconciliation.processed_by = actor
    if notes:
        existing = f"{reconciliation.notes}\n" if reconciliation.notes else ""
        reconciliation.notes = f"{existing}[Xác nhận]: {notes}".strip()

    reconciliation.save()
    return reconciliation


def cod_reconciliation_mark_paid(
    *,
    reconciliation: CODReconciliation,
    actor: User,
    notes: str = "",
) -> CODReconciliation:
    """
    Marks the reconciliation payout as transferred/paid, completing payment on all attached orders.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    if not is_admin:
        raise OrderPermissionDeniedError("Chỉ Quản trị viên mới có quyền thanh toán quyết toán COD.")

    if reconciliation.status == CODReconciliationStatus.PAID:
        raise CODReconciliationError("Bảng kê đối soát này đã được thanh toán trước đó.")

    with transaction.atomic():
        reconciliation.status = CODReconciliationStatus.PAID
        reconciliation.paid_at = timezone.now()
        reconciliation.processed_by = actor
        if notes:
            existing = f"{reconciliation.notes}\n" if reconciliation.notes else ""
            reconciliation.notes = f"{existing}[Thanh toán]: {notes}".strip()

        reconciliation.save()

        # Update all attached orders to PAID
        reconciliation.orders.update(payment_status=OrderPaymentStatus.PAID)

        return reconciliation


def order_return_create(
    *,
    order: Order,
    actor: User,
    reason: str,
    reason_detail: str = "",
    fee_payer: str = ReturnFeePayer.SHOP,
    return_shipping_fee: Decimal | float | int = 0,
    refund_amount: Decimal | float | int = 0,
    return_address: str = "",
    pickup_address: str = "",
    notes: str = "",
) -> OrderReturn:
    """
    Creates a new RMA return request for an order.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_owner = order.customer_id == actor.id

    if not is_admin and not is_owner:
        raise OrderPermissionDeniedError("Bạn không có quyền yêu cầu hoàn trả cho đơn hàng này.")

    if order.status in [OrderStatus.CANCELLED]:
        raise OrderReturnError("Không thể yêu cầu hoàn trả cho đơn hàng đã bị hủy.")

    active_statuses = [
        ReturnStatus.REQUESTED,
        ReturnStatus.APPROVED,
        ReturnStatus.PICKING_UP,
        ReturnStatus.IN_RETURN_TRANSIT,
    ]
    if order.returns.filter(status__in=active_statuses).exists():
        raise OrderReturnError("Đơn hàng này hiện đã có một yêu cầu hoàn trả đang được xử lý.")

    ret_address = (return_address or order.sender_address).strip()
    p_address = (pickup_address or order.receiver_address).strip()

    ref_amt = Decimal(str(refund_amount or 0))
    if ref_amt <= Decimal("0") and order.cod_amount > Decimal("0") and order.status == OrderStatus.DELIVERED:
        ref_amt = order.cod_amount

    ret_fee = Decimal(str(return_shipping_fee or 0))
    if ret_fee <= Decimal("0"):
        ret_fee = order.shipping_fee or Decimal("25000.00")

    order_return = OrderReturn.objects.create(
        order=order,
        requested_by=actor,
        reason=reason,
        reason_detail=reason_detail.strip(),
        fee_payer=fee_payer,
        return_shipping_fee=ret_fee,
        refund_amount=ref_amt,
        return_address=ret_address,
        pickup_address=p_address,
        notes=notes.strip(),
        status=ReturnStatus.REQUESTED,
    )

    order_add_tracking_event(
        order=order,
        status=order.status,
        note=f"Tạo yêu cầu hoàn trả {order_return.return_code}: {order_return.get_reason_display()}",
        actor=actor,
    )

    return order_return


def order_return_approve(
    *,
    order_return: OrderReturn,
    actor: User,
    driver_id: int | None = None,
    return_shipping_fee: Decimal | float | int | None = None,
    refund_amount: Decimal | float | int | None = None,
    notes: str = "",
) -> OrderReturn:
    """
    Approves an RMA return request, optionally assigning a driver and updating fees.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    if not is_admin:
        raise OrderPermissionDeniedError("Chỉ Quản trị viên mới có quyền duyệt yêu cầu hoàn trả.")

    if order_return.status != ReturnStatus.REQUESTED:
        raise OrderReturnError(
            f"Không thể duyệt yêu cầu đang ở trạng thái '{order_return.get_status_display()}'."
        )

    order_return.status = ReturnStatus.APPROVED
    order_return.approved_at = timezone.now()

    if driver_id:
        driver = User.objects.filter(id=driver_id, role=UserRole.DRIVER, is_active=True).first()
        if not driver:
            raise DriverAssignmentError("Tài xế được chỉ định không hợp lệ hoặc không hoạt động.")
        order_return.assigned_driver = driver

    if return_shipping_fee is not None:
        order_return.return_shipping_fee = Decimal(str(return_shipping_fee))
    if refund_amount is not None:
        order_return.refund_amount = Decimal(str(refund_amount))

    if notes:
        existing = f"{order_return.notes}\n" if order_return.notes else ""
        order_return.notes = f"{existing}[Phê duyệt]: {notes}".strip()

    order_return.save()

    order_add_tracking_event(
        order=order_return.order,
        status=order_return.order.status,
        note=f"Yêu cầu hoàn trả {order_return.return_code} đã được duyệt.",
        actor=actor,
    )

    return order_return


def order_return_reject(
    *,
    order_return: OrderReturn,
    actor: User,
    reason: str = "",
) -> OrderReturn:
    """
    Rejects an RMA return request with a specified reason.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    if not is_admin:
        raise OrderPermissionDeniedError("Chỉ Quản trị viên mới có quyền từ chối yêu cầu hoàn trả.")

    if order_return.status != ReturnStatus.REQUESTED:
        raise OrderReturnError("Chỉ có thể từ chối yêu cầu hoàn trả đang chờ duyệt.")

    order_return.status = ReturnStatus.REJECTED
    if reason:
        existing = f"{order_return.notes}\n" if order_return.notes else ""
        order_return.notes = f"{existing}[Từ chối]: {reason}".strip()

    order_return.save()

    order_add_tracking_event(
        order=order_return.order,
        status=order_return.order.status,
        note=f"Yêu cầu hoàn trả {order_return.return_code} đã bị từ chối. {f'Lý do: {reason}' if reason else ''}".strip(),
        actor=actor,
    )

    return order_return


def order_return_update_status(
    *,
    order_return: OrderReturn,
    new_status: str,
    actor: User,
    location: str = "",
    note: str = "",
) -> OrderReturn:
    """
    Updates the transit / resolution status of an order return.
    """
    is_admin = actor.is_superuser or getattr(actor, "role", None) == UserRole.ADMIN
    is_assigned_driver = (
        getattr(actor, "role", None) == UserRole.DRIVER
        and order_return.assigned_driver_id == actor.id
    )

    if not is_admin and not is_assigned_driver:
        raise OrderPermissionDeniedError("Bạn không có quyền cập nhật tiến trình trả hàng này.")

    if order_return.status in [ReturnStatus.RETURNED_TO_SENDER, ReturnStatus.REJECTED, ReturnStatus.CANCELLED]:
        raise OrderReturnError(
            f"Yêu cầu hoàn trả đã ở trạng thái kết thúc '{order_return.get_status_display()}', không thể đổi trạng thái."
        )

    if not is_admin and is_assigned_driver:
        allowed_driver_statuses = [
            ReturnStatus.PICKING_UP,
            ReturnStatus.IN_RETURN_TRANSIT,
            ReturnStatus.RETURNED_TO_SENDER,
        ]
        if new_status not in allowed_driver_statuses:
            raise OrderPermissionDeniedError(f"Tài xế không có quyền chuyển sang trạng thái '{new_status}'.")

    with transaction.atomic():
        order_return.status = new_status
        if new_status == ReturnStatus.RETURNED_TO_SENDER:
            order_return.completed_at = timezone.now()

        if note:
            existing = f"{order_return.notes}\n" if order_return.notes else ""
            order_return.notes = f"{existing}[Cập nhật]: {note}".strip()

        order_return.save()

        if new_status in [ReturnStatus.IN_RETURN_TRANSIT, ReturnStatus.RETURNED_TO_SENDER]:
            order = order_return.order
            if order.status != OrderStatus.RETURNED:
                order.status = OrderStatus.RETURNED
                order.save()

        order_add_tracking_event(
            order=order_return.order,
            status=order_return.order.status,
            location=location,
            note=note or f"Tiến trình trả hàng {order_return.return_code}: {order_return.get_status_display()}",
            actor=actor,
        )

        return order_return



